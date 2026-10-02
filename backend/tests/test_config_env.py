import pytest

from app.config.access import AccessConfig
from app.config.database import DEFAULT_DATABASE_URL, DatabaseConfig
from app.config.env import REPO_ROOT
from app.config.trust import TrustConfig

ENV_VARS = ("DATABASE_URL", "LEDGER_HMAC_KEY", "ASR_MODE", "SMS_PROVIDER")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_database_default_is_anchored_to_repo_root() -> None:
    assert (REPO_ROOT / "tasks.py").exists()
    assert DatabaseConfig().url == DEFAULT_DATABASE_URL
    assert DEFAULT_DATABASE_URL == f"sqlite:///{(REPO_ROOT / 'jallekha.db').as_posix()}"


def test_database_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    assert DatabaseConfig().url == "sqlite:///:memory:"


def test_blank_env_value_uses_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "   ")
    assert DatabaseConfig().url == DEFAULT_DATABASE_URL


def test_ledger_key_has_no_default_and_is_hidden(monkeypatch: pytest.MonkeyPatch) -> None:
    assert TrustConfig().ledger_hmac_key is None
    monkeypatch.setenv("LEDGER_HMAC_KEY", "local-test-key")
    config = TrustConfig()
    assert config.ledger_hmac_key == "local-test-key"
    assert "local-test-key" not in repr(config)


def test_access_defaults_need_no_ml_install() -> None:
    config = AccessConfig()
    assert config.asr_mode == "fallback"
    assert config.sms_provider == "fake"


def test_asr_mode_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASR_MODE", "indicconformer")
    assert AccessConfig().asr_mode == "indicconformer"


def test_unknown_asr_mode_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ASR_MODE", "whisper")
    with pytest.raises(ValueError, match="ASR_MODE"):
        AccessConfig()


def test_unknown_sms_provider_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMS_PROVIDER", "twilio")
    with pytest.raises(ValueError, match="SMS_PROVIDER"):
        AccessConfig()
