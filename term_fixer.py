"""
product-name-normalizer: normalize product/tool names in generated text.

Design goals:
- Core logic is stdlib-only (so other projects can `import fix_terms` with zero deps).
- Optional MCP server entrypoint for Claude Code / MCP clients.
- Central, user-scope storage: ~/.claude/data/product-terms.json (overridable in tests via env var).
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable


DEFAULT_TERMS: dict[str, list[str]] = {
    "Claude Code": ["Cloudcode", "Cloud Code", "ClaudeCode"],
    "Antigravity": ["Antygravity", "AntiGravity", "Anti-gravity"],
    "Wispr Flow": ["Wisprflow", "WisprFlow", "Whispr Flow"],
    "Cursor": ["Curser"],
    "Windsurf": ["WindSurf", "Wind Surf"],
    "Firecrawl": ["Fire Crawl", "FireCrawl"],
    "Snowflake": ["SnowFlake"],
    "Lovable": ["Loveable"],
    "Replit": ["Repl.it"],
}

_TAG_SPLIT_RE = re.compile(r"(<[^>]+>)")


def _get_terms_path() -> Path:
    override = os.environ.get("TERM_FIXER_TERMS_PATH")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude" / "data" / "product-terms.json"


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _ensure_terms_file(path: Path) -> None:
    if path.exists():
        return
    _atomic_write_json(path, DEFAULT_TERMS)


def _load_terms(path: Path) -> dict[str, list[str]]:
    _ensure_terms_file(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Terms file must be a JSON object: {path}")

    out: dict[str, list[str]] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            out[k] = list(v)
        else:
            # Be permissive: treat invalid entries as "no variants".
            out[k] = []
    return out


def _dedup_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        key = x.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def _compile_rules(terms: dict[str, list[str]]) -> list[tuple[re.Pattern[str], str, int]]:
    rules: list[tuple[re.Pattern[str], str, int]] = []
    for correct, variants in terms.items():
        if not isinstance(correct, str) or not correct.strip():
            continue

        # Include the canonical term itself to normalize casing (idempotent when already correct).
        all_variants = _dedup_preserve_order([correct, *variants])
        for v in all_variants:
            vv = v.strip()
            if not vv:
                continue
            pat = re.compile(rf"\b{re.escape(vv)}\b", re.IGNORECASE)
            rules.append((pat, correct, len(vv)))

    # Longest first to avoid partial overlaps (best-effort).
    rules.sort(key=lambda t: t[2], reverse=True)
    return rules


@lru_cache(maxsize=16)
def _compiled_rules_for(path_str: str, mtime_ns: int) -> tuple[tuple[re.Pattern[str], str], ...]:
    # mtime_ns is part of cache key: edits to the JSON invalidate the compiled rules automatically.
    terms = _load_terms(Path(path_str))
    rules = _compile_rules(terms)
    return tuple((pat, repl) for pat, repl, _ in rules)


def fix_terms(text: str) -> str:
    """Normalize product/tool names in `text` using the user-scope terms dictionary."""
    if not text:
        return text

    path = _get_terms_path()
    _ensure_terms_file(path)
    try:
        mtime_ns = path.stat().st_mtime_ns
    except FileNotFoundError:
        # If the file disappears between ensure+stat, re-create and retry.
        _ensure_terms_file(path)
        mtime_ns = path.stat().st_mtime_ns

    rules = _compiled_rules_for(str(path), mtime_ns)

    # Avoid mutating HTML tags/attributes: only apply replacements to text segments.
    parts = _TAG_SPLIT_RE.split(text)
    for i, part in enumerate(parts):
        if not part or (part.startswith("<") and part.endswith(">")):
            continue
        updated = part
        for pat, repl in rules:
            updated = pat.sub(repl, updated)
        parts[i] = updated

    return "".join(parts)


def add_term(correct: str, wrong_variants: list[str]) -> str:
    """Add/update a term mapping in the terms dictionary.

    Persisted to ~/.claude/data/product-terms.json (or TERM_FIXER_TERMS_PATH override).
    """
    correct = (correct or "").strip()
    if not correct:
        raise ValueError("`correct` must be a non-empty string")

    variants = [(v or "").strip() for v in (wrong_variants or [])]
    variants = [v for v in variants if v]

    path = _get_terms_path()
    terms = _load_terms(path)

    # Reuse existing key if it matches case-insensitively.
    canonical_key = next((k for k in terms.keys() if k.casefold() == correct.casefold()), correct)
    existing = terms.get(canonical_key, [])

    merged = _dedup_preserve_order([*existing, *variants])
    merged = [v for v in merged if v.casefold() != canonical_key.casefold()]
    terms[canonical_key] = merged

    _atomic_write_json(path, terms)
    return "ok"


def _run_mcp_server() -> None:
    # Import MCP deps only when running as a server. This keeps `import term_fixer` stdlib-only.
    from mcp.server.fastmcp import FastMCP  # type: ignore

    mcp = FastMCP("product-name-normalizer")

    @mcp.tool(name="fix_terms", description="Correct product/tool names in the given text.")
    def _fix_terms_tool(text: str) -> str:
        return fix_terms(text)

    @mcp.tool(name="add_term", description="Add or extend a term mapping in the local terms dictionary.")
    def _add_term_tool(correct: str, wrong_variants: list[str]) -> str:
        return add_term(correct, wrong_variants)

    mcp.run()


if __name__ == "__main__":
    _run_mcp_server()
