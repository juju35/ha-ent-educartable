"""The translation files are kept in sync with English."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

TRANSLATIONS = Path(__file__).parent.parent / "custom_components" / "educartable" / "translations"


def _keys(value, prefix: str = "") -> set[str]:
    if isinstance(value, dict):
        keys: set[str] = set()
        for name, sub in value.items():
            keys |= _keys(sub, f"{prefix}.{name}" if prefix else name)
        return keys
    return {prefix}


def _load(name: str) -> dict:
    return json.loads((TRANSLATIONS / name).read_text(encoding="utf-8"))


def test_english_exists() -> None:
    assert (TRANSLATIONS / "en.json").is_file()


@pytest.mark.parametrize("other", [p.name for p in TRANSLATIONS.glob("*.json") if p.name != "en.json"])
def test_same_keys_as_english(other: str) -> None:
    english = _keys(_load("en.json"))
    translated = _keys(_load(other))
    assert translated == english, f"{other} differs: {english ^ translated}"
