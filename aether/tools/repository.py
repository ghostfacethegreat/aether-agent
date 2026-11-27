"""Local repository indexing, safe unified-diff handling, and constrained test execution."""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import threading
from pathlib import Path, PurePosixPath

from aether.coding.index import PersistentRepositoryIndex
from aether.coding.symbols import SYMBOL_INDEX_VERSION, extract_symbols
from aether.errors import ToolError
from aether.home import aether_home
from aether.utils import parse_bool

_IGNORED_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", ".venv", "venv", "env", "node_modules",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", "dist", "build", ".idea",
}
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(?:.*)$")
_TEST_MODULE = re.compile(r"^test_[A-Za-z0-9_]{1,100}$")
_MAX_PATCH_BYTES = 256 * 1024
_MAX_PATCH_FILES = 16
_INDEX_LOCK = threading.Lock()


def _bounded_int(config, key, default, minimum, maximum):
    try:
        value = int(config.get(key, default))
    except (AttributeError, TypeError, ValueError, OverflowError):
        value = default
    return max(minimum, min(maximum, value))


def _workspace(context):
    try:
        root = Path(context.get("workspace") or Path.cwd()).expanduser().resolve()
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ToolError(f"Could not resolve workspace: {exc}") from exc
    if not root.is_dir():
        raise ToolError("Workspace directory does not exist")
    return root


def _root_path(context, raw="."):
    workspace = _workspace(context)
    candidate = Path(str(raw or ".")).expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    try:
        lexical = candidate.absolute()
        relative = lexical.relative_to(workspace)
        current = workspace
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise ToolError("Repository index refuses symlink paths")
        resolved = lexical.resolve(strict=True)
    except ValueError as exc:
        raise ToolError("Repository path must remain inside the configured workspace") from exc
    except (OSError, RuntimeError) as exc:
        raise ToolError(f"Repository path does not exist: {raw}") from exc
    if resolved != workspace and workspace not in resolved.parents:
        raise ToolError("Repository path must remain inside the configured workspace")
    if not resolved.is_dir():
        raise ToolError("Repository index root must be a directory")
    return resolved


def _ignore_rules(directory, base):
    """Read one bounded .gitignore file and retain the directory it applies to."""
    path = directory / ".gitignore"
    if not path.is_file() or path.is_symlink():
        return []
    try:
        if path.stat().st_size > 64 * 1024:
            return []
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    rules = []
    for line in lines:
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        negated = value.startswith("!")
        if negated:
            value = value[1:]
        if not value:
            continue
        directory_only = value.endswith("/")
        # Preserve a leading slash before removing separators so negated anchored
        # patterns (for example, !/keep.txt) remain scoped to this directory.
        anchored = value.startswith("/")
        value = value.strip("/")
        if not value:
            continue
        # Git treats slash-containing patterns as relative to this ignore file.
        # A leading slash is also anchored to this directory.
        rules.append((base, value, negated, directory_only, anchored or "/" in value))
    return rules


def _matches_ignore(relative, is_dir, rules):
    """Evaluate inherited root/nested rules in order, including directory ancestors."""
    ignored = False
    for base, pattern, negated, directory_only, path_pattern in rules:
        if base:
            prefix = base + "/"
            if not relative.startswith(prefix):
                continue
            scoped = relative[len(prefix):]
        else:
            scoped = relative

        parts = scoped.split("/")
        candidates = ["/".join(parts[:index]) for index in range(1, len(parts) + 1)]
        # A directory-only rule matches directory ancestors, never a same-named file.
        if directory_only and not is_dir:
            candidates = candidates[:-1]
        if not candidates:
            continue

        if path_pattern:
            matched = any(fnmatch.fnmatchcase(candidate, pattern) for candidate in candidates)
        else:
            matched = any(
                fnmatch.fnmatchcase(part, pattern)
                for candidate in candidates
                for part in candidate.split("/")
            )
        if matched:
            ignored = not negated
    return ignored


def _walk_files(root, max_files):
    stack = [(root, [])]
    emitted = 0
    while stack and emitted < max_files:
        directory, inherited_rules = stack.pop()
        base = directory.relative_to(root).as_posix()
        if base == ".":
            base = ""
        rules = inherited_rules + _ignore_rules(directory, base)
        try:
            with os.scandir(directory) as iterator:
                entries = sorted(iterator, key=lambda item: item.name, reverse=True)
        except OSError:
            continue
        for entry in entries:
            if emitted >= max_files:
                break
            try:
                if entry.is_symlink():
                    continue
                path = Path(entry.path)
                relative = path.relative_to(root).as_posix()
                if entry.is_dir(follow_symlinks=False):
                    if entry.name in _IGNORED_DIRS or _matches_ignore(relative, True, rules):
                        continue
                    stack.append((path, rules))
                elif entry.is_file(follow_symlinks=False) and not _matches_ignore(relative, False, rules):
                    emitted += 1
                    yield path, relative
            except OSError:
                continue


def repo_index(args, context):
    """Build a bounded index or search filenames, snippets, and declarations."""
    config = context.get("config") or {}
    root = _root_path(context, args.get("root") or ".")
    action = str(args.get("action") or "summary").strip().lower()
    if action not in ("summary", "search", "symbols", "index"):
        raise ToolError("repo_index action must be 'summary', 'search', 'symbols', or 'index'")
    query = str(args.get("query") or "").strip()
    if action in ("search", "symbols") and not query:
        raise ToolError(f"repo_index {action} requires a non-empty query")

    max_files = _bounded_int(config, "repository_index.max_files", 3000, 1, 20000)
    max_file_bytes = _bounded_int(config, "repository_index.max_file_bytes", 262144, 256, 4 * 1024 * 1024)
    max_total_bytes = _bounded_int(config, "repository_index.max_total_bytes", 8 * 1024 * 1024, 1024, 64 * 1024 * 1024)
    result_limit = _bounded_int(config, "repository_index.max_results", 40, 1, 100)
    persistent = parse_bool(config.get("repository_index.persistent"), True)
    if action == "index" and not persistent:
        raise ToolError("repo_index action 'index' requires repository_index.persistent")
    if persistent and action in ("index", "symbols"):
        return _persistent_repo_index(context, root, action, query, config)

    query_lower = query.casefold()
    indexed, matches, symbol_matches = [], [], []
    total_bytes = skipped_large = skipped_binary = 0
    truncated = False

    for path, relative in _walk_files(root, max_files):
        try:
            size = path.stat().st_size
            if size > max_file_bytes:
                skipped_large += 1
                continue
            if total_bytes + size > max_total_bytes:
                truncated = True
                break
            raw = path.read_bytes()
            if b"\x00" in raw:
                skipped_binary += 1
                continue
            content = raw.decode("utf-8", "replace")
        except OSError:
            continue
        total_bytes += len(raw)
        lines = content.splitlines()
        indexed.append({
            "path": relative,
            "bytes": len(raw),
            "lines": len(lines),
            "extension": path.suffix.lower(),
        })
        if action == "search":
            name_match = query_lower in relative.casefold()
            snippets = []
            if not name_match:
                for number, line in enumerate(lines, start=1):
                    if query_lower in line.casefold():
                        snippets.append({"line": number, "text": line[:240]})
                        if len(snippets) >= 3:
                            break
            if name_match or snippets:
                matches.append({"path": relative, "name_match": name_match, "snippets": snippets})
                if len(matches) >= result_limit:
                    truncated = True
                    break
        elif action == "symbols":
            for symbol in extract_symbols(relative, content):
                if query_lower in symbol["name"].casefold():
                    symbol_matches.append(symbol)
                    if len(symbol_matches) >= result_limit:
                        truncated = True
                        break
            if truncated:
                break

    result = {
        "root": str(root),
        "files_indexed": len(indexed),
        "bytes_indexed": total_bytes,
        "skipped_large": skipped_large,
        "skipped_binary": skipped_binary,
        "truncated": truncated,
        "ignore_source": "root and nested .gitignore files plus built-in generated/vendor directories",
        "persistent": False,
    }
    if action == "search":
        result.update({"query": query, "matches": matches, "match_count": len(matches)})
    elif action == "symbols":
        result.update({"query": query, "symbols": symbol_matches, "match_count": len(symbol_matches)})
    else:
        result["files"] = indexed[: min(result_limit, 100)]
        result["file_list_truncated"] = len(indexed) > len(result["files"])
    return result


def _persistent_repo_index_locked(context, root, action, query, config):
    max_files = _bounded_int(config, "repository_index.max_files", 3000, 1, 20000)
    max_file_bytes = _bounded_int(config, "repository_index.max_file_bytes", 262144, 256, 4 * 1024 * 1024)
    max_total_bytes = _bounded_int(config, "repository_index.max_total_bytes", 8 * 1024 * 1024, 1024, 64 * 1024 * 1024)
    result_limit = _bounded_int(config, "repository_index.max_results", 40, 1, 100)
    max_symbols = _bounded_int(config, "repository_index.max_index_symbols", 20000, 1, 200000)
    signature = json.dumps({
        "max_files": max_files,
        "max_file_bytes": max_file_bytes,
        "max_total_bytes": max_total_bytes,
        "max_symbols": max_symbols,
        "symbol_index_version": SYMBOL_INDEX_VERSION,
    }, sort_keys=True, separators=(",", ":"))
    cancel_event = context.get("cancel_event")

    def cancelled():
        return cancel_event is not None and bool(getattr(cancel_event, "is_set", lambda: False)())

    home = context.get("home") or aether_home()
    index = PersistentRepositoryIndex(Path(home))
    stored, stale = index.snapshot(str(root), signature)
    all_stale = stale is None
    records, changed = [], set()
    total_bytes = skipped_large = skipped_binary = 0
    truncated = False

    for path, relative in _walk_files(root, max_files):
        if cancelled():
            raise ToolError("repo_index cancelled")
        info = stored.get(relative)
        try:
            metadata = path.stat()
        except OSError:
            continue
        if metadata.st_size > max_file_bytes:
            skipped_large += 1
            continue
        if total_bytes + metadata.st_size > max_total_bytes:
            truncated = True
            break
        is_stale = (
            all_stale or info is None
            or int(info["size"]) != metadata.st_size
            or int(info["mtime_ns"]) != metadata.st_mtime_ns
            or int(info.get("ctime_ns", 0)) != metadata.st_ctime_ns
        )
        if is_stale:
            if path.is_symlink():
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            size = len(raw)
            if size > max_file_bytes:
                skipped_large += 1
                continue
            if total_bytes + size > max_total_bytes:
                truncated = True
                break
            if b"\x00" in raw:
                skipped_binary += 1
                continue
            content = raw.decode("utf-8", "replace")
            content_hash = hashlib.sha256(raw).hexdigest()
            if info and info["content_hash"] == content_hash:
                lines = int(info["lines"])
                symbols = []
            else:
                lines = len(content.splitlines())
                symbols = extract_symbols(relative, content)
                changed.add(relative)
            record = {
                "path": relative, "size": size, "mtime_ns": metadata.st_mtime_ns,
                "ctime_ns": metadata.st_ctime_ns, "content_hash": content_hash, "lines": lines,
                "extension": path.suffix.lower(), "symbols": symbols,
            }
        else:
            record = {
                "path": relative, "size": int(info["size"]), "mtime_ns": int(info["mtime_ns"]),
                "ctime_ns": int(info.get("ctime_ns", 0)), "content_hash": info["content_hash"],
                "lines": int(info["lines"]), "extension": info["extension"], "symbols": [],
            }
        total_bytes += record["size"]
        records.append(record)

    if cancelled():
        raise ToolError("repo_index cancelled")
    refresh = index.sync(str(root), signature, records, changed, max_symbols, cancel_event=cancel_event)
    result = {
        "root": str(root),
        "files_indexed": len(records),
        "bytes_indexed": total_bytes,
        "skipped_large": skipped_large,
        "skipped_binary": skipped_binary,
        "truncated": truncated,
        "ignore_source": "root and nested .gitignore files plus built-in generated/vendor directories",
        "persistent": True,
        "refresh": refresh,
    }
    if action == "symbols":
        symbols, query_truncated = index.query_symbols(str(root), query, result_limit)
        result["truncated"] = result["truncated"] or query_truncated
        result.update({"query": query, "symbols": symbols, "match_count": len(symbols)})
    return result


def _persistent_repo_index(context, root, action, query, config):
    with _INDEX_LOCK:
        return _persistent_repo_index_locked(context, root, action, query, config)


def _patch_path(raw, prefix):
    value = str(raw or "").strip()
    if value == "/dev/null" or not value:
        raise ToolError("Patch creation/deletion is not supported yet; modify existing files only")
    if value.startswith('"') or value.endswith('"'):
        raise ToolError("Quoted patch paths are not supported; use simple relative paths")
    if value.startswith(prefix + "/"):
        value = value[len(prefix) + 1:]
    if "\\" in value or "\x00" in value or value.startswith("/"):
        raise ToolError(f"Unsafe patch path: {raw}")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise ToolError(f"Unsafe patch path: {raw}")
    pure = PurePosixPath(value)
    if not pure.parts:
        raise ToolError("Patch path is empty")
    return pure


def _resolve_patch_file(workspace, relative):
    current = workspace
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ToolError(f"Patch refuses symlink paths: {relative.as_posix()}")
    try:
        resolved = current.resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ToolError(f"Patch target does not exist: {relative.as_posix()}") from exc
    if resolved != workspace and workspace not in resolved.parents:
        raise ToolError(f"Patch target escapes workspace: {relative.as_posix()}")
    if not resolved.is_file():
        raise ToolError(f"Patch target is not a regular file: {relative.as_posix()}")
    return resolved


def _apply_hunks(original, hunks, relative):
    newline = "\r\n" if "\r\n" in original else "\n"
    final_newline = original.endswith(("\n", "\r"))
    source, output, cursor = original.splitlines(), [], 0
    for hunk in hunks:
        start = hunk["old_start"]
        position = 0 if start == 0 else start - 1
        if position < cursor or position > len(source):
            raise ToolError(f"Patch hunk is out of order or outside {relative}")
        output.extend(source[cursor:position])
        cursor = position
        old_seen = new_seen = 0
        for line in hunk["lines"]:
            prefix, value = line[0], line[1:]
            if prefix == " ":
                if cursor >= len(source) or source[cursor] != value:
                    raise ToolError(f"Patch context does not match {relative} at original line {cursor + 1}")
                output.append(value)
                cursor += 1
                old_seen += 1
                new_seen += 1
            elif prefix == "-":
                if cursor >= len(source) or source[cursor] != value:
                    raise ToolError(f"Patch removal does not match {relative} at original line {cursor + 1}")
                cursor += 1
                old_seen += 1
            elif prefix == "+":
                output.append(value)
                new_seen += 1
        if old_seen != hunk["old_count"] or new_seen != hunk["new_count"]:
            raise ToolError(f"Patch hunk line counts are invalid for {relative}")
    output.extend(source[cursor:])
    return newline.join(output) + (newline if final_newline else "")


def _parse_patch(patch):
    if not isinstance(patch, str) or not patch.strip():
        raise ToolError("A non-empty unified diff is required")
    if len(patch.encode("utf-8")) > _MAX_PATCH_BYTES:
        raise ToolError(f"Patch exceeds {_MAX_PATCH_BYTES} bytes")
    lines, files, index = patch.splitlines(), [], 0
    while index < len(lines):
        if not lines[index].startswith("--- "):
            index += 1
            continue
        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            raise ToolError("Unified diff is missing its +++ file header")
        old_path = _patch_path(lines[index][4:].split("\t", 1)[0], "a")
        new_path = _patch_path(lines[index + 1][4:].split("\t", 1)[0], "b")
        if old_path != new_path:
            raise ToolError("Patch renames are not supported; old and new paths must match")
        relative = old_path.as_posix()
        if any(item["relative"] == relative for item in files):
            raise ToolError(f"Patch contains duplicate file section: {relative}")
        index += 2
        hunks = []
        while index < len(lines) and not lines[index].startswith("--- "):
            match = _HUNK_HEADER.match(lines[index])
            if not match:
                index += 1
                continue
            old_start = int(match.group(1))
            old_count = int(match.group(2) or 1)
            new_count = int(match.group(4) or 1)
            index += 1
            hunk_lines, old_seen, new_seen = [], 0, 0
            while index < len(lines):
                if old_seen >= old_count and new_seen >= new_count:
                    break
                line = lines[index]
                if line.startswith("@@ "):
                    break
                if line.startswith("\\ No newline at end of file"):
                    index += 1
                    continue
                if not line or line[0] not in (" ", "+", "-"):
                    break
                hunk_lines.append(line)
                if line[0] in (" ", "-"):
                    old_seen += 1
                if line[0] in (" ", "+"):
                    new_seen += 1
                index += 1
            if old_seen != old_count or new_seen != new_count:
                raise ToolError(f"Patch hunk declares {old_count}/{new_count} lines but contains {old_seen}/{new_seen}")
            hunks.append({"old_start": old_start, "old_count": old_count, "new_count": new_count, "lines": hunk_lines})
        if not hunks:
            raise ToolError(f"Patch contains no hunks for {relative}")
        files.append({"relative": relative, "path": old_path, "hunks": hunks})
        if len(files) > _MAX_PATCH_FILES:
            raise ToolError(f"Patch exceeds the {_MAX_PATCH_FILES}-file limit")
    if not files:
        raise ToolError("No unified-diff file sections were found")
    return files


def _prepare_patch(patch, context):
    workspace, prepared = _workspace(context), []
    for item in _parse_patch(patch):
        target = _resolve_patch_file(workspace, item["path"])
        try:
            if target.stat().st_size > 4 * 1024 * 1024:
                raise ToolError(f"Patch target exceeds the 4 MiB safety limit: {item['relative']}")
            raw = target.read_bytes()
            original = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ToolError(f"Patch target is not UTF-8 text: {item['relative']}") from exc
        except OSError as exc:
            raise ToolError(f"Could not read patch target {item['relative']}: {exc}") from exc
        if b"\x00" in raw:
            raise ToolError(f"Patch refuses binary file: {item['relative']}")
        updated = _apply_hunks(original, item["hunks"], item["relative"]).encode("utf-8")
        prepared.append({
            "relative": item["relative"], "path": target, "original": raw, "updated": updated,
            "mode": stat.S_IMODE(target.stat().st_mode),
            "original_sha256": hashlib.sha256(raw).hexdigest(),
            "updated_sha256": hashlib.sha256(updated).hexdigest(),
        })
    return prepared


def patch_preview(args, context):
    """Validate a unified diff and report expected changes without writing files."""
    prepared = _prepare_patch(str(args.get("patch") or ""), context)
    return {
        "valid": True,
        "writes_performed": False,
        "files": [{
            "path": item["relative"],
            "old_sha256": item["original_sha256"],
            "new_sha256": item["updated_sha256"],
            "old_bytes": len(item["original"]),
            "new_bytes": len(item["updated"]),
        } for item in prepared],
    }


def _atomic_write(path, data, mode):
    fd, temp_name = tempfile.mkstemp(prefix=".aether-patch-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, mode)
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def patch_apply(args, context):
    """Apply only after every target passes preflight; the executor enforces approval."""
    prepared = _prepare_patch(str(args.get("patch") or ""), context)
    for item in prepared:
        try:
            current = item["path"].read_bytes()
        except OSError as exc:
            raise ToolError(f"Patch target changed or disappeared: {item['relative']}") from exc
        if hashlib.sha256(current).hexdigest() != item["original_sha256"]:
            raise ToolError(f"Patch target changed after preview: {item['relative']}")
    applied = []
    try:
        for item in prepared:
            _atomic_write(item["path"], item["updated"], item["mode"])
            applied.append(item)
    except OSError as exc:
        rollback_errors = []
        for item in reversed(applied):
            try:
                _atomic_write(item["path"], item["original"], item["mode"])
            except OSError as rollback_exc:
                rollback_errors.append(f"{item['relative']}: {rollback_exc}")
        detail = f"; rollback errors: {', '.join(rollback_errors)}" if rollback_errors else ""
        raise ToolError(f"Patch write failed: {exc}{detail}") from exc
    return {
        "applied": True,
        "files_changed": len(prepared),
        "files": [item["relative"] for item in prepared],
        "note": "All targets were validated before writing; user approval is enforced by the tool permission policy.",
    }


def test_run(args, context):
    """Run fixed repository test/check commands without a user-controlled shell string."""
    workspace = _workspace(context)
    config = context.get("config") or {}
    mode = str(args.get("mode") or "suite").strip().lower()
    timeout = _bounded_int(config, "repository_index.test_timeout", 300, 5, 600)
    python = sys.executable
    if mode == "suite":
        tests_dir = workspace / "tests"
        if tests_dir.is_symlink() or not tests_dir.is_dir():
            raise ToolError("tests/ directory is missing or is a symlink")
        try:
            has_tests = any(
                item.is_file() and not item.is_symlink() and item.name.startswith("test_") and item.suffix == ".py"
                for item in tests_dir.iterdir()
            )
        except OSError as exc:
            raise ToolError(f"Could not inspect tests/: {exc}") from exc
        if not has_tests:
            raise ToolError("No top-level test_*.py modules were found; refusing a zero-test pass")
        command = [python, "-m", "unittest", "discover", "-s", "tests"]
    elif mode == "compile":
        command = [python, "-m", "compileall", "-q", "aether", "tests"]
    elif mode == "module":
        module = str(args.get("module") or "").strip()
        if not _TEST_MODULE.fullmatch(module):
            raise ToolError("module mode requires a test module named test_*.py without a path")
        tests_dir = workspace / "tests"
        test_file = tests_dir / f"{module}.py"
        if tests_dir.is_symlink() or test_file.is_symlink() or not test_file.is_file():
            raise ToolError(f"Test module not found: tests/{module}.py")
        command = [python, "-m", "unittest", f"tests.{module}"]
    elif mode == "check":
        script = workspace / "scripts" / "check.sh"
        if script.is_symlink() or not script.is_file():
            raise ToolError("scripts/check.sh does not exist or is a symlink")
        command = ["bash", "scripts/check.sh"]
    else:
        raise ToolError("test_run mode must be suite, module, compile, or check")
    try:
        completed = subprocess.run(
            command, cwd=str(workspace), capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "PYTHONUNBUFFERED": "1"}, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or "", exc.stderr or ""
        return {
            "command": command, "exit_code": None, "timed_out": True, "timeout_seconds": timeout,
            "output": (str(stdout) + str(stderr))[-12000:],
        }
    except OSError as exc:
        raise ToolError(f"Could not start test command: {exc}") from exc
    return {
        "command": command, "exit_code": completed.returncode, "timed_out": False,
        "output": ((completed.stdout or "") + (completed.stderr or ""))[-12000:],
    }
