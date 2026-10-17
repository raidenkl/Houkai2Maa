"""`tools/shared/version.py` 的版本/tag 一致性判断。"""

from __future__ import annotations

from shared.version import is_valid, matches_tag, normalize, parse


def test_parse_basic() -> None:
    assert parse("1.2.3") == (1, 2, 3)
    assert parse("v1.2.3") == (1, 2, 3)
    assert parse("2.0.0-dev.1") == (2, 0, 0)
    assert parse("2.0.0-ci.20260101-abc1234") == (2, 0, 0)


def test_parse_rejects_bad_values() -> None:
    assert parse("") is None
    assert parse("1.2") is None
    assert parse("version-1.2.3") is None
    assert is_valid("1.2.3") is True
    assert is_valid("1.2.3.4") is False


def test_normalize_strips_v_prefix() -> None:
    assert normalize(" v2.0.0 ") == "2.0.0"
    assert normalize("2.0.0") == "2.0.0"


def test_matches_tag() -> None:
    assert matches_tag("2.0.0", "v2.0.0") is True
    assert matches_tag("2.0.0", "2.0.0") is True
    assert matches_tag("2.0.0", "v2.0.1") is False
    assert matches_tag("2.0.0-dev.1", "v2.0.0") is False
    assert matches_tag("2.0.0-dev.1", "v2.0.0-dev.1") is True
