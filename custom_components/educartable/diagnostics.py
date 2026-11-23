"""Diagnostics for Educartable."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD_SECRET, CONF_USERNAME_SECRET
from .coordinator import EducartableConfigEntry

REDACT = {CONF_USERNAME, CONF_PASSWORD, CONF_USERNAME_SECRET, CONF_PASSWORD_SECRET, "parent_id", "name", "firstname"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: EducartableConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = asdict(coordinator.data) if coordinator.data else {}
    return {
        "entry": {"data": async_redact_data(dict(entry.data), REDACT), "options": dict(entry.options)},
        "data": async_redact_data(data, REDACT),
    }
