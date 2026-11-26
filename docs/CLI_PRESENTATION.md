# CLI presentation

Aether's interactive CLI uses an original blue, 3D block-letter treatment inspired by the visual direction of Patorjk's Text to ASCII Art Generator (TAAG). The renderer is implemented in Aether's Python standard-library CLI; it does not load a website, make network requests, or add a runtime package.

## Relationship to TAAG

TAAG is powered by the open-source [figlet.js](https://github.com/patorjk/figlet.js/) FIGlet renderer. The selected **ACID 3D Blue** font in the supplied link is a TheDraw ANSI font, not a conventional FIGlet font. TheDraw files can carry character-specific color information and have a different format from FIGlet fonts. Patorjk's July 2026 write-up notes that the redistribution rights for the collected TheDraw font files are unclear: [Adding TheDraw Fonts to TAAG](https://patorjk.com/blog/2026/07/17/adding-thedraw-fonts-to-taag/).

For that reason, Aether does not copy TAAG's minified site bundle or redistribute the ACID 3D Blue font file. Instead, this project uses an original built-in block-letter masthead, ANSI blue/cyan colors, framed runtime details, response labels, and a chat prompt with ASCII fallbacks. No third-party code or font data is copied into the renderer.

## Configuration

```bash
aether config set terminal.theme "acid-blue"          # default
aether config set terminal.theme "classic"
aether config set terminal.theme "mono"
aether config set terminal.unicode false
aether config set terminal.show_banner false
aether config set terminal.show_dashboard false
aether config set terminal.show_response_labels false
```

Environment overrides:

- `NO_COLOR=1` disables ANSI color.
- `AETHER_ASCII=1` forces ASCII-safe glyphs.

Settings are presentation-only. They do not change model behavior, prompts, tools, approvals, provider selection, budgets, or stored session data.

## Runtime constraints

The renderer uses only Python's standard library. It remains compatible with Python 3.10+, checks terminal width, and avoids emitting Unicode block art when ASCII mode is selected or the output encoding cannot represent it. Spinner animation is used only when stdout is an interactive terminal.

## Streamed output

Streamed model text, including visible reasoning deltas, passes through `render.sanitize_untrusted()` before it is written to stdout, so terminal escape and control sequences embedded in model output are stripped on that path. This describes the implemented streamed-output path only; it is not a blanket invariant that all terminal text is escape-safe. Tool output, repository files, web pages, memories, and agent reports remain untrusted data handled by their own boundaries.
