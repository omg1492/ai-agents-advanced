from src.services.template_service import TemplateService

def test_system_prompt_includes_profile_write_guidance(monkeypatch):
    # Ensure flag true
    monkeypatch.setenv("USER_PROFILE_ENABLED", "true")
    ts = TemplateService()
    rendered = ts.render_template("system_prompt.j2", {
        "memory_write_profile_enabled": True,
        "config": None,
        "user_profile": '{"diet": {"vegetarian": true}}',
    })
    assert "memory_write_profile" in rendered
    assert "patch the persistent user profile" in rendered
    # New mandatory confirmation instruction
    assert "applied=true" in rendered


def test_system_prompt_omits_profile_write_guidance_when_disabled(monkeypatch):
    monkeypatch.delenv("USER_PROFILE_ENABLED", raising=False)
    ts = TemplateService()
    rendered = ts.render_template("system_prompt.j2", {
        "memory_write_profile_enabled": False,
        "config": None,
    })
    # Should not contain tool guidance block wording
    assert "patch the persistent user profile" not in rendered
