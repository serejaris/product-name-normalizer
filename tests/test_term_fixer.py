import sys
from pathlib import Path

# Some Python/pytest setups do not include the project root on sys.path when
# running via the `pytest` entrypoint script. Ensure the module is importable.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_fix_terms_basic(tmp_path, monkeypatch):
    monkeypatch.setenv("TERM_FIXER_TERMS_PATH", str(tmp_path / "product-terms.json"))

    import term_fixer

    text = "Cloudcode, Antygravity, Wisprflow"
    out = term_fixer.fix_terms(text)

    assert "Claude Code" in out
    assert "Antigravity" in out
    assert "Wispr Flow" in out


def test_fix_terms_does_not_touch_html_attributes(tmp_path, monkeypatch):
    monkeypatch.setenv("TERM_FIXER_TERMS_PATH", str(tmp_path / "product-terms.json"))

    import term_fixer

    text = '<a href="https://example.com/Cloudcode">Cloudcode</a>'
    out = term_fixer.fix_terms(text)

    assert out == '<a href="https://example.com/Cloudcode">Claude Code</a>'


def test_add_term_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("TERM_FIXER_TERMS_PATH", str(tmp_path / "product-terms.json"))

    import term_fixer

    assert term_fixer.add_term("FooBar", ["Foobar", "Foo Bar"]) == "ok"
    assert term_fixer.fix_terms("I like foobar") == "I like FooBar"


def test_env_override_path_is_respected(tmp_path, monkeypatch):
    # Ensure we never touch the real ~/.claude/data in tests.
    terms_path = tmp_path / "some" / "nested" / "terms.json"
    monkeypatch.setenv("TERM_FIXER_TERMS_PATH", str(terms_path))

    import term_fixer

    out = term_fixer.fix_terms("Cloudcode")
    assert out == "Claude Code"
    assert terms_path.exists()
