"""Diagnostics for Educartable: the config entry and the shape of the last update, without anything personal."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import CONF_NOTIFY, CONF_PASSWORD_SECRET, CONF_USERNAME_SECRET
from .coordinator import EducartableConfigEntry

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, CONF_USERNAME_SECRET, CONF_PASSWORD_SECRET, CONF_NOTIFY, "unique_id"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: EducartableConfigEntry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    homework = [h for items in data.homework.values() for h in items] if data else []
    messages = [*data.carnet, *data.news] if data else []
    # Children, teachers, messages and homework are about real children: only counts leave Home Assistant.
    return {
        "entry": async_redact_data(
            {"data": dict(entry.data), "options": dict(entry.options), "unique_id": entry.unique_id}, TO_REDACT
        ),
        "coordinator": {
            "update_interval": str(coordinator.update_interval),
            "last_update_success": coordinator.last_update_success,
            "homework_days": coordinator.homework_days,
        },
        "data": {
            "pupils": len(data.pupils) if data else 0,
            "homework": len(homework),
            "homework_done": sum(1 for h in homework if h["done"]),
            "carnet": len(data.carnet) if data else 0,
            "news": len(data.news) if data else 0,
            "achievements": sorted({m["achievement"] for m in [*messages, *homework] if m["achievement"]}),
            "medias": sum(len(m["medias"]) for m in [*messages, *homework]),
            "surveys": sum(1 for m in messages if m.get("survey")),
            "slots": sum(len(m.get("slots") or []) for m in messages),
            "commentable": sum(1 for m in messages if m.get("commentable")),
            "documents": len(data.documents) if data else 0,
            "documents_to_sign": sum(1 for d in data.documents if d["to_sign"]) if data else 0,
            "stale": data.stale if data else [],
        },
    }
