"""Unit tests for runtime.config — env parsing that backs every security gate."""
from __future__ import annotations

from runtime.config import (
    _env_bool,
    _env_float,
    load_config,
    mutation_denied_payload,
)


class TestEnvBool:
    def test_default_when_unset(self):
        assert _env_bool("ASTRBOT_TEST_NOPE") is False
        assert _env_bool("ASTRBOT_TEST_NOPE", True) is True

    def test_truthy_values(self, monkeypatch):
        for v in ("1", "true", "TRUE", "Yes", "on", " true "):
            monkeypatch.setenv("ASTRBOT_TEST_B", v)
            assert _env_bool("ASTRBOT_TEST_B") is True, v

    def test_falsy_values(self, monkeypatch):
        # SECURITY: "false"-like strings must never enable a gate
        for v in ("0", "false", "False", "no", "off", "", "  ", "yes!", "enabled"):
            monkeypatch.setenv("ASTRBOT_TEST_B", v)
            assert _env_bool("ASTRBOT_TEST_B") is False, v

    def test_empty_uses_default_not_false(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_TEST_B", "")
        assert _env_bool("ASTRBOT_TEST_B", True) is True


class TestEnvFloat:
    def test_default_and_parse(self, monkeypatch):
        assert _env_float("ASTRBOT_TEST_F", 15.0) == 15.0
        monkeypatch.setenv("ASTRBOT_TEST_F", "20.5")
        assert _env_float("ASTRBOT_TEST_F", 15.0) == 20.5

    def test_garbage_falls_back_no_crash(self, monkeypatch):
        # bad env must not crash the MCP process
        monkeypatch.setenv("ASTRBOT_TEST_F", "twenty")
        assert _env_float("ASTRBOT_TEST_F", 15.0) == 15.0


class TestLoadConfig:
    def test_defaults_all_gates_closed(self):
        # conftest clears ASTRBOT_*: everything must default to safe/off
        cfg = load_config()
        assert cfg.enabled is False
        assert cfg.allow_mutations is False
        assert cfg.allow_chat_probe is False
        assert cfg.token_configured is False
        assert cfg.auth_mode == "api_key"
        assert cfg.timeout == 15.0
        assert cfg.chat_config_name == "plugin_dev_skill"

    def test_enabled_requires_base_url(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://192.168.1.50:6185")
        assert load_config().enabled is True

    def test_mutations_gate_string_false(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://192.168.1.50:6185")
        monkeypatch.setenv("ASTRBOT_ALLOW_MUTATIONS", "false")
        cfg = load_config()
        assert cfg.allow_mutations is False

    def test_public_dict_never_leaks_token(self, monkeypatch):
        secret = "abk_super_secret_value_123"
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://192.168.1.50:6185")
        monkeypatch.setenv("ASTRBOT_TOKEN", secret)
        cfg = load_config()
        pub = cfg.public_dict()
        import json

        assert secret not in json.dumps(pub)
        assert pub["token_configured"] is True

    def test_capabilities_follow_gates(self, monkeypatch):
        monkeypatch.setenv("ASTRBOT_BASE_URL", "http://192.168.1.50:6185")
        pub = load_config().public_dict()
        caps = pub["capabilities"]
        assert caps["read_plugins"] is True
        # mutations off → all write capabilities false
        for key in ("uninstall", "install_path", "ensure_plugin_dev_skill",
                    "reload_enable_config_write", "chat_sessions_cleanup"):
            assert caps[key] is False, key


class TestMutationDenied:
    def test_payload_shape(self):
        p = mutation_denied_payload("chat_sessions_cleanup")
        assert p["error_kind"] == "mutations_disabled"
        assert "chat_sessions_cleanup" in str(p)
