"""The Educartable integration: homework, liaison book and news of an EDUMOOV family account."""

from __future__ import annotations

import hashlib
import logging
from functools import partial
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import Event, HassJob, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import ConfigType

from .api import EducartableApi
from .config_flow import clean_options, new_session
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    BADGE_FILENAME,
    CARD_FILENAME,
    CONF_HIDE_HEADER,
    CONF_HOMEWORK_DAYS,
    CONF_PANEL_TABS,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_PANEL,
    DEFAULT_SHOW_PANEL,
    DOMAIN,
    FRONTEND_URL,
    HIDE_HEADER_CHOICES,
    PANEL_FILENAME,
    PANEL_ICON,
    PANEL_TABS,
    PANEL_URL_PATH,
    SERVICE_REFRESH,
)
from .coordinator import EducartableConfigEntry, EducartableCoordinator
from .secret import SecretNotFoundError, async_credentials

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]
# Seconds before deciding on the panel after an unload: long enough for a reload to set the entry up again.
PANEL_REMOVE_DELAY = 10
FRONTEND_DIR = Path(__file__).parent / "frontend"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the card and the panel, and register the refresh service and the websocket commands once."""
    await hass.http.async_register_static_paths([StaticPathConfig(FRONTEND_URL, str(FRONTEND_DIR), True)])
    await _async_register_card(hass)
    # The sidebar badge, on every page: the number of things to deal with on the panel's sidebar item.
    _base, badge_url = await _file_url(hass, BADGE_FILENAME)
    add_extra_js_url(hass, badge_url)
    websocket_api.async_register_command(hass, ws_settings)
    websocket_api.async_register_command(hass, ws_update_settings)

    async def refresh(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_failed",
                translation_placeholders={"error": str(coordinator.last_exception or "unknown error")},
            )

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, refresh, REFRESH_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: EducartableConfigEntry) -> bool:
    try:
        username, password = await async_credentials(hass, entry.data)
    except SecretNotFoundError as err:
        raise ConfigEntryNotReady(str(err)) from err
    api = EducartableApi(new_session(hass), username, password)
    coordinator = EducartableCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await _async_update_panel(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EducartableConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        # Not removed at once: a reload (options saved from the panel) unloads then sets the entry up again, and
        # removing the panel in between sends the open panel back to the home page. Decided a moment later.
        async_call_later(
            hass, PANEL_REMOVE_DELAY, HassJob(partial(_async_check_panel_later, hass), cancel_on_shutdown=True)
        )
    return unloaded


async def _file_url(hass: HomeAssistant, filename: str) -> tuple[str, str]:
    """Base URL of a frontend file, and the same URL versioned with the file's hash for the browser cache."""
    path = FRONTEND_DIR / filename
    digest = await hass.async_add_executor_job(
        lambda: hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest()[:8]
    )
    base_url = f"{FRONTEND_URL}/{filename}"
    return base_url, f"{base_url}?v={digest}"


async def _async_register_card(hass: HomeAssistant) -> None:
    """Add the card to the dashboard resources, as ha-parcel does."""
    base_url, url = await _file_url(hass, CARD_FILENAME)

    async def register(_event: Event | None = None) -> None:
        resources, mode = _lovelace_resources(hass.data.get("lovelace"))
        if resources is None or mode != "storage":
            add_extra_js_url(hass, url)
            return
        try:
            if not resources.loaded:
                await resources.async_load()
                resources.loaded = True
            existing = [item for item in resources.async_items() if item.get("url", "").split("?")[0] == base_url]
            if not existing:
                await resources.async_create_item({"res_type": "module", "url": url})
                _LOGGER.info("Educartable card added to dashboard resources: %s", url)
            elif existing[0].get("url") != url:
                await resources.async_update_item(existing[0]["id"], {"res_type": "module", "url": url})
            for duplicate in existing[1:]:
                await resources.async_delete_item(duplicate["id"])
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "Could not add the Educartable card to dashboard resources (%s). Add %s manually "
                "in Settings > Dashboards > Resources (JavaScript module)",
                err,
                url,
            )
            add_extra_js_url(hass, url)

    if hass.is_running:
        await register()
    else:
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, register)


def _lovelace_resources(lovelace: Any) -> tuple[Any, str]:
    """Lovelace resources and their mode: hass.data["lovelace"] is a dict before 2025.2, then a dataclass."""
    if isinstance(lovelace, dict):
        return lovelace.get("resources"), lovelace.get("resource_mode", lovelace.get("mode", "storage"))
    return getattr(lovelace, "resources", None), getattr(
        lovelace, "resource_mode", getattr(lovelace, "mode", "storage")
    )


async def _async_update_panel(hass: HomeAssistant, setting_up: EducartableConfigEntry) -> None:
    """Show the sidebar panel while at least one account wants it (the one being set up is not LOADED yet)."""
    entries = [*_loaded_entries(hass), setting_up]
    wanted = any(e.options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL) for e in entries)
    registered = PANEL_URL_PATH in hass.data.get(frontend.DATA_PANELS, {})
    if wanted and not registered:
        _base, url = await _file_url(hass, PANEL_FILENAME)
        # The panel reuses the card file's helpers and translations: it imports the same versioned URL.
        _base, card_url = await _file_url(hass, CARD_FILENAME)
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name="educartable-panel",
            sidebar_title="Educartable",
            sidebar_icon=PANEL_ICON,
            module_url=url,
            require_admin=False,
            config={"card_url": card_url},
        )
    elif not wanted and registered:
        frontend.async_remove_panel(hass, PANEL_URL_PATH)


@callback
def _async_check_panel_later(hass: HomeAssistant, _now: Any) -> None:
    """Remove the panel once no loaded account wants it any more (entry removed, panel option turned off)."""
    wanted = any(e.options.get(CONF_SHOW_PANEL, DEFAULT_SHOW_PANEL) for e in _loaded_entries(hass))
    if not wanted and PANEL_URL_PATH in hass.data.get(frontend.DATA_PANELS, {}):
        frontend.async_remove_panel(hass, PANEL_URL_PATH)


def _loaded_entries(hass: HomeAssistant) -> list[EducartableConfigEntry]:
    return [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]


async def _async_reload(hass: HomeAssistant, entry: EducartableConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _get_coordinator(hass: HomeAssistant, entry_id: str | None) -> EducartableCoordinator:
    entries = _loaded_entries(hass)
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_account")
    if len(entries) > 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="several_accounts")
    return entries[0].runtime_data


@websocket_api.websocket_command({vol.Required("type"): "educartable/settings"})
@callback
def ws_settings(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """The accounts and their options, for the panel's Settings tab."""
    accounts = [
        {"entry_id": e.entry_id, "title": e.title, "options": clean_options(e.options)} for e in _loaded_entries(hass)
    ]
    connection.send_result(msg["id"], {"accounts": accounts, "admin": connection.user.is_admin})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "educartable/settings/update",
        vol.Required("entry_id"): str,
        vol.Required("options"): vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL): vol.Coerce(int),
                vol.Optional(CONF_HOMEWORK_DAYS): vol.Coerce(int),
                vol.Optional(CONF_SHOW_PANEL): bool,
                vol.Optional(CONF_PANEL_TABS): [vol.In(PANEL_TABS)],
                vol.Optional(CONF_HIDE_HEADER): vol.In(HIDE_HEADER_CHOICES),
            }
        ),
    }
)
@callback
def ws_update_settings(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    """Save an account's options from the panel; the update listener reloads it."""
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    if entry is None or entry.domain != DOMAIN:
        connection.send_error(msg["id"], "not_found", "Unknown Educartable account")
        return
    options = clean_options({**entry.options, **msg["options"]})
    hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(msg["id"], {"options": options})
