"""The Educartable integration: homework, liaison book and news of an EDUMOOV family account."""

from __future__ import annotations

import hashlib
import logging
import re
from functools import partial
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import quote

import voluptuous as vol
from aiohttp import web
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import KEY_HASS, KEY_HASS_USER, HomeAssistantView, StaticPathConfig
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import Event, HassJob, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType

from .api import EducartableApi, EducartableError
from .config_flow import clean_options, new_session, notify_choices
from .const import (
    ATTR_CONFIG_ENTRY_ID,
    ATTR_MESSAGE_ID,
    ATTR_NAME,
    BADGE_FILENAME,
    CARD_FILENAME,
    CONF_HIDE_HEADER,
    CONF_HOMEWORK_DAYS,
    CONF_NOTIFY,
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
    SERVICE_MARK_READ,
    SERVICE_REFRESH,
    SERVICE_SIGN,
)
from .coordinator import EducartableConfigEntry, EducartableCoordinator
from .secret import SecretNotFoundError, async_credentials

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.CALENDAR, Platform.SENSOR, Platform.TODO]
# Seconds before deciding on the panel after an unload: long enough for a reload to set the entry up again.
PANEL_REMOVE_DELAY = 10
FRONTEND_DIR = Path(__file__).parent / "frontend"
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})
MESSAGE_ID = vol.All(cv.string, vol.Strip, vol.Length(min=1))
SIGN_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_MESSAGE_ID): MESSAGE_ID,
        vol.Required(ATTR_NAME): vol.All(cv.string, vol.Strip, vol.Length(min=3)),
    }
)
MARK_READ_SCHEMA = vol.Schema(
    {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string, vol.Required(ATTR_MESSAGE_ID): MESSAGE_ID}
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Serve the card and the panel, and register the refresh service and the websocket commands once."""
    await hass.http.async_register_static_paths([StaticPathConfig(FRONTEND_URL, str(FRONTEND_DIR), True)])
    await _async_register_card(hass)
    # The sidebar badge, on every page: the number of things to deal with on the panel's sidebar item.
    _base, badge_url = await _file_url(hass, BADGE_FILENAME)
    add_extra_js_url(hass, badge_url)
    websocket_api.async_register_command(hass, ws_settings)
    websocket_api.async_register_command(hass, ws_update_settings)
    websocket_api.async_register_command(hass, ws_homework_done)
    hass.http.register_view(EducartableFileView())

    async def refresh(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        await coordinator.async_refresh()
        if not coordinator.last_update_success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="refresh_failed",
                translation_placeholders={"error": str(coordinator.last_exception or "unknown error")},
            )

    async def achieve(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call.data.get(ATTR_CONFIG_ENTRY_ID))
        try:
            await coordinator.async_achieve(call.data[ATTR_MESSAGE_ID], call.data.get(ATTR_NAME, ""))
        except EducartableError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="action_failed", translation_placeholders={"error": str(err)}
            ) from err

    hass.services.async_register(DOMAIN, SERVICE_REFRESH, refresh, REFRESH_SCHEMA)
    # Signing and marking read act on the portal with the parent's account: administrators only (a child's Home
    # Assistant account must not sign their own liaison book). The card and the panel hide the buttons from others.
    async_register_admin_service(hass, DOMAIN, SERVICE_SIGN, achieve, SIGN_SCHEMA)
    async_register_admin_service(hass, DOMAIN, SERVICE_MARK_READ, achieve, MARK_READ_SCHEMA)
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
    notify = notify_choices(hass, [])
    connection.send_result(
        msg["id"], {"accounts": accounts, "notify_services": notify, "admin": connection.user.is_admin}
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "educartable/settings/update",
        vol.Required("entry_id"): str,
        vol.Required("options"): vol.Schema(
            {
                vol.Optional(CONF_SCAN_INTERVAL): vol.Coerce(int),
                vol.Optional(CONF_HOMEWORK_DAYS): vol.Coerce(int),
                vol.Optional(CONF_NOTIFY): [str],
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


# Ticking homework acts on the portal with the parent's account: administrators only, like signing.
@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "educartable/homework_done",
        vol.Required("config_entry_id"): str,
        vol.Required("child_id"): str,
        vol.Required("homework_id"): str,
        vol.Required("done"): bool,
    }
)
@websocket_api.async_response
async def ws_homework_done(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Tick or untick a homework from the card or the panel."""
    try:
        coordinator = _get_coordinator(hass, msg["config_entry_id"])
        await coordinator.async_set_homework_done(msg["child_id"], msg["homework_id"], msg["done"])
    except (ServiceValidationError, EducartableError) as err:
        connection.send_error(msg["id"], "failed", str(err))
        return
    connection.send_result(msg["id"])


# Types a browser shows without running anything: shown in the card and the panel, every other file is downloaded.
INLINE_TYPES = frozenset({"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp", "text/plain"})
SANDBOX_POLICY = "sandbox; default-src 'none'; img-src 'self'; style-src 'unsafe-inline'"
# Signatures of the inline types: portals often serve attachments as application/octet-stream.
MAGIC_TYPES = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)


def sniff_type(body: bytes, declared: str, filename: str) -> str:
    """Type a file is served as: its signature first, then the portal's type, then its extension."""
    for magic, kind in MAGIC_TYPES:
        if body.startswith(magic):
            return kind
    if body[:4] == b"RIFF" and body[8:12] == b"WEBP":
        return "image/webp"
    declared = declared.split(";")[0].strip().lower()
    if declared and declared != "application/octet-stream":
        return declared
    # Without a signature, an image or a PDF is not one: only text is taken on its extension.
    return "text/plain" if filename.lower().endswith(".txt") else "application/octet-stream"


def file_name(name: str) -> str:
    """A served file's name, without the characters a header cannot carry."""
    text = (name or "").encode("utf-8", "ignore").decode("utf-8")
    return re.sub(r'[\x00-\x1f"\\/]', "", text).strip()[:150] or "file"


class EducartableFileView(HomeAssistantView):
    """An attachment (media) of a message, fetched with the account's session.

    The browser has no portal session of its own: the card asks Home Assistant for a signed URL of this view
    (auth/sign_path) and shows it (image, PDF) or downloads it. Administrators only (a signed URL carries the user who
    signed it).
    """

    url = "/api/educartable/file/{entry_id}"
    name = "api:educartable:file"
    requires_auth = True

    async def get(self, request: web.Request, entry_id: str) -> web.Response:
        hass: HomeAssistant = request.app[KEY_HASS]
        user = request.get(KEY_HASS_USER)
        if user is None or not user.is_admin:
            return web.Response(status=HTTPStatus.FORBIDDEN, text="Administrators only")
        try:
            coordinator = _get_coordinator(hass, entry_id)
        except ServiceValidationError as err:
            return web.Response(status=HTTPStatus.BAD_REQUEST, text=str(err))
        media_id = request.query.get("media", "")
        try:
            body, content_type = await coordinator.async_media(media_id)
        except EducartableError as err:
            _LOGGER.warning("Educartable media %s not fetched: %s", media_id, err)
            return web.Response(status=HTTPStatus.BAD_GATEWAY, text=str(err))
        filename = file_name(request.query.get("name", "") or media_id)
        kind = sniff_type(body, content_type, filename)
        # Served from Home Assistant's origin: only inert types are shown. Anything else (HTML, SVG, scripts) is a
        # plain download under a sandbox policy. A PDF gets no sandbox: browsers refuse to draw a sandboxed PDF.
        inline = kind in INLINE_TYPES
        headers = {
            "Content-Disposition": f"{'inline' if inline else 'attachment'}; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "private, max-age=3600",
            "X-Content-Type-Options": "nosniff",
        }
        if kind != "application/pdf":
            headers["Content-Security-Policy"] = SANDBOX_POLICY
        return web.Response(body=body, content_type=kind if inline else "application/octet-stream", headers=headers)
