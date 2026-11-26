## Summary

Describe the change in a few sentences.

## Related issue

Closes #

## Why this change?

What user problem does it solve?

## Verification

List the exact commands run and their results. Do not claim checks passed if they were not run on this commit.

- [ ] Focused tests added or updated
- [ ] `python3 -m compileall -q aether tests`
- [ ] `python3 -m unittest discover -s tests -v`
- [ ] `bash scripts/check.sh`
- [ ] `bash scripts/test_install.sh`
- [ ] `git diff --check`

## Safety, privacy, and cost

Describe any changes to tool permissions, approvals, path/URL handling, secret handling, persistent user data, provider usage, or billing. Write "No change" when none apply.

## Documentation and compatibility

- [ ] User-facing docs updated
- [ ] Configuration and migration implications documented
- [ ] Known limitations updated when relevant
- [ ] No credentials, private data, or local state included
