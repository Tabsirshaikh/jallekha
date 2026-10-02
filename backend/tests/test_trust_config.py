import copy
import dataclasses
import pickle

from app.config.trust import TRUST_CONFIG, TrustConfig


def test_trust_config_supports_asdict_deepcopy_pickle_and_hash() -> None:
    as_dict = dataclasses.asdict(TRUST_CONFIG)
    assert dict(as_dict["dedup_window_hours"])["leak"] == 168
    assert copy.deepcopy(TRUST_CONFIG) == TRUST_CONFIG
    assert pickle.loads(pickle.dumps(TRUST_CONFIG)) == TRUST_CONFIG
    assert hash(TRUST_CONFIG) == hash(TrustConfig(ledger_hmac_key=TRUST_CONFIG.ledger_hmac_key))


def test_dedup_windows_are_read_only() -> None:
    windows = TRUST_CONFIG.dedup_window_hours
    assert isinstance(windows, tuple)
    assert dict(windows) == {
        "no_water": 48,
        "tanker_missed": 48,
        "dirty_water": 48,
        "leak": 168,
        "other": 168,
    }
