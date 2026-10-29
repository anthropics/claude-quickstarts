"""
Tests for PromptTemplateRegistry (Fáze 21).
All offline — no external dependencies.
"""
import pytest

from core.prompt_templates import PromptTemplateRegistry, _extract_variables


@pytest.fixture
def reg():
    return PromptTemplateRegistry()


# ── Variable extraction ────────────────────────────────────────────────────────

def test_extract_no_vars():
    assert _extract_variables("Hello world") == []


def test_extract_single_var():
    assert _extract_variables("Hello {{name}}") == ["name"]


def test_extract_multiple_vars():
    vars_ = _extract_variables("{{a}} plus {{b}} equals {{c}}")
    assert vars_ == ["a", "b", "c"]


def test_extract_deduplicates():
    vars_ = _extract_variables("{{x}} and {{x}} again")
    assert vars_ == ["x"]


# ── Registration ──────────────────────────────────────────────────────────────

def test_register_returns_uuid(reg):
    tid = reg.register("greet", "Hello {{name}}")
    assert tid is not None and len(tid) == 36


def test_register_empty_name_raises(reg):
    with pytest.raises(ValueError, match="name"):
        reg.register("", "some template")


def test_register_empty_template_raises(reg):
    with pytest.raises(ValueError, match="template"):
        reg.register("foo", "")


def test_template_count(reg):
    reg.register("a", "text {{x}}")
    reg.register("b", "text {{y}}")
    assert reg.template_count() == 2


def test_register_same_name_bumps_version(reg):
    reg.register("t", "v1 {{x}}")
    reg.register("t", "v2 {{x}}")
    reg.register("t", "v3 {{x}}")
    versions = [d["version"] for d in reg.get_by_name("t")]
    assert sorted(versions) == [1, 2, 3]


# ── Retrieval ─────────────────────────────────────────────────────────────────

def test_get_returns_dict(reg):
    tid = reg.register("greet", "Hi {{name}}", description="A greeting")
    t = reg.get(tid)
    assert t["name"] == "greet"
    assert t["description"] == "A greeting"
    assert "name" in t["variables"]


def test_get_missing_returns_none(reg):
    assert reg.get("ghost") is None


def test_get_by_name_returns_newest_first(reg):
    reg.register("foo", "v1")
    reg.register("foo", "v2")
    items = reg.get_by_name("foo")
    assert items[0]["version"] == 2
    assert items[1]["version"] == 1


def test_get_by_name_unknown_returns_empty(reg):
    assert reg.get_by_name("nonexistent") == []


def test_get_latest(reg):
    reg.register("bar", "v1")
    reg.register("bar", "v2")
    latest = reg.get_latest("bar")
    assert latest["version"] == 2


def test_get_latest_unknown_returns_none(reg):
    assert reg.get_latest("nonexistent") is None


def test_list_templates(reg):
    reg.register("p", "{{x}}")
    reg.register("q", "{{y}}")
    names = {t["name"] for t in reg.list_templates()}
    assert names == {"p", "q"}


def test_list_templates_by_tag(reg):
    reg.register("a", "{{x}}", tags=["chat"])
    reg.register("b", "{{y}}", tags=["rag"])
    chat = reg.list_templates(tag="chat")
    assert len(chat) == 1
    assert chat[0]["name"] == "a"


# ── Deletion ──────────────────────────────────────────────────────────────────

def test_delete_template(reg):
    tid = reg.register("d", "{{x}}")
    assert reg.delete(tid) is True
    assert reg.get(tid) is None


def test_delete_missing_returns_false(reg):
    assert reg.delete("ghost") is False


# ── Render ────────────────────────────────────────────────────────────────────

def test_render_substitutes_variables(reg):
    tid = reg.register("greet", "Hello {{name}}, you are {{age}} years old.")
    result = reg.render(tid, name="Alice", age=30)
    assert result == "Hello Alice, you are 30 years old."


def test_render_no_variables(reg):
    tid = reg.register("static", "No variables here.")
    assert reg.render(tid) == "No variables here."


def test_render_missing_variable_raises(reg):
    tid = reg.register("partial", "Hello {{name}} from {{city}}")
    with pytest.raises(ValueError, match="Missing template variables"):
        reg.render(tid, name="Bob")  # city missing


def test_render_missing_template_raises(reg):
    with pytest.raises(KeyError):
        reg.render("ghost", x=1)


def test_render_extra_kwargs_ignored(reg):
    tid = reg.register("simple", "Hello {{name}}")
    result = reg.render(tid, name="Alice", extra="ignored")
    assert result == "Hello Alice"
