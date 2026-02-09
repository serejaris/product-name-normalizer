# product-name-normalizer

Local (user-scope) normalization of product/tool names for AI-generated text.

This exists because LLMs (and chat participants) routinely misspell tool names and the mistakes
propagate into digests/posts: `Cloudcode` -> `Claude Code`, `Antygravity` -> `Antigravity`, `Wisprflow` -> `Wispr Flow`, etc.

The goal is to make this a single, reusable component:
- as a **Python module** (stdlib-only at import time)
- as a **user-scope MCP server** (for Claude Code / skills / other MCP clients)

## Context / Why

In `tg-digest-opus` the digest for **2026-02-08** was produced with incorrect product names.
Fixing this *inside prompts* is fragile; it keeps leaking in from:
- raw chat messages (people write names wrong)
- LLM completions (the model "learns" the wrong spelling from context)

So the fix is centralized and deterministic: a dictionary-driven normalizer that any consumer can call.

## Python usage (zero deps)

```python
from term_fixer import fix_terms

text = fix_terms("Cloudcode vs Cursor")
```

Dictionary is stored in `data/product-terms.json` (override with `TERM_FIXER_TERMS_PATH`).

### Dictionary format

`product-terms.json` is a JSON map:

```json
{
  "Claude Code": ["Cloudcode", "ClaudeCode"],
  "Antigravity": ["Antygravity", "Anti-gravity"]
}
```

### Add / extend a term

```python
from term_fixer import add_term

add_term("Claude Code", ["Cloudcode", "ClaudeCode"])
```

Or edit `data/product-terms.json` manually (it is a simple JSON map).

## How It Works

- Dictionary format: `{ "Correct Name": ["wrong1", "wrong2"] }`
- Replacements: case-insensitive regex with word boundaries (`\\b...\\b`)
- HTML safety: it avoids touching tag/attribute content by only rewriting *text segments* outside `<...>`
- It applies longest variants first to reduce partial-overlap issues.
- Compiled regex rules are cached and invalidated automatically when `product-terms.json` changes (mtime-based).

## Files In This Repo

- `term_fixer.py`: stdlib-only core + MCP entrypoint
- `data/product-terms.json`: the dictionary used by default
- `scripts/smoke_mcp.py`: end-to-end MCP smoke test

Non-goals (for now):
- fuzzy matching / spelling suggestions
- language-aware morphology

## MCP server (Claude Code)

Run locally via stdio:

```bash
uv -q --directory ~/Documents/GitHub/product-name-normalizer run term_fixer.py
```

Add to Claude Code (user scope):

```bash
claude mcp add product-name-normalizer -s user -- uv -q --directory ~/Documents/GitHub/product-name-normalizer run term_fixer.py
```

Tools:
- `fix_terms(text: str) -> str`
- `add_term(correct: str, wrong_variants: list[str]) -> str`

## Integration (tg-digest-opus)

`tg-digest-opus` loads this repo in best-effort mode (no hard dependency).

- Default lookup path: `~/Documents/GitHub/product-name-normalizer`
- Override: set `TERM_FIXER_REPO=/path/to/product-name-normalizer`

## Development

Run tests:

```bash
uv run pytest
```

Smoke test MCP (spawns the server and calls tools over stdio):

```bash
uv run python scripts/smoke_mcp.py
```
