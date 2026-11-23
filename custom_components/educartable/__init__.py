"""The Educartable integration: homework, liaison book and news of an EDUMOOV family account."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .api import EducartableApi
from .config_flow import new_session
from .const import ATTR_CONFIG_ENTRY_ID, DOMAIN, SERVICE_REFRESH
from .coordinator import EducartableConfigEntry, EducartableCoordinator
from .secret import SecretNotFoundError, async_credentials

PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the refresh service once."""

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
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EducartableConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: EducartableConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


def _get_coordinator(hass: HomeAssistant, entry_id: str | None) -> EducartableCoordinator:
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    if not entries:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_account")
    if len(entries) > 1:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="several_accounts")
    return entries[0].runtime_data
