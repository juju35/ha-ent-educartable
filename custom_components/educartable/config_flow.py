"""Config flow for Educartable."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigEntryState, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import EducartableApi, EducartableAuthError, EducartableError, EducartableOTPRequired
from .const import (
    CONF_HOMEWORK_DAYS,
    CONF_PASSWORD_SECRET,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME_SECRET,
    DEFAULT_HOMEWORK_DAYS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .secret import SecretNotFoundError, async_credentials

PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
CONF_TOTP = "totp"


def new_session(hass: HomeAssistant) -> aiohttp.ClientSession:
    """A session with its own cookie jar, kept apart from other integrations."""
    return async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())


async def validate(
    hass: HomeAssistant, username: str, password: str, totp: str | None
) -> tuple[dict[str, Any] | None, str | None]:
    """Log in once: the user info, or an error key."""
    session = new_session(hass)
    try:
        api = EducartableApi(session, username, password, totp)
        await api.login()
        return await api.user_info(), None
    except EducartableOTPRequired:
        return None, "otp_required"
    except EducartableAuthError:
        return None, "invalid_auth"
    except EducartableError:
        return None, "cannot_connect"
    finally:
        session.detach()


def _secret_name(value: Any) -> str:
    return str(value or "").strip().removeprefix("!secret").strip()


def credential_fields(defaults: Mapping[str, Any]) -> dict:
    return {
        vol.Optional(CONF_USERNAME, default=defaults.get(CONF_USERNAME, "")): str,
        vol.Optional(CONF_USERNAME_SECRET, default=defaults.get(CONF_USERNAME_SECRET, "")): str,
        vol.Optional(CONF_PASSWORD): PASSWORD,
        vol.Optional(CONF_PASSWORD_SECRET, default=defaults.get(CONF_PASSWORD_SECRET, "")): str,
        vol.Optional(CONF_TOTP): str,
    }


async def credentials(
    hass: HomeAssistant, user_input: Mapping[str, Any]
) -> tuple[dict[str, str], tuple[str, str] | None, str | None]:
    """The credentials part of the entry data, the resolved (username, password), and an error key."""
    data: dict[str, str] = {}
    for key, secret, error in (
        (CONF_USERNAME, CONF_USERNAME_SECRET, "username_or_secret"),
        (CONF_PASSWORD, CONF_PASSWORD_SECRET, "password_or_secret"),
    ):
        value = str(user_input.get(key) or "")
        value = value.strip() if key == CONF_USERNAME else value
        name = _secret_name(user_input.get(secret))
        if bool(value.strip()) == bool(name):
            return {}, None, error
        data.update({secret: name} if name else {key: value})
    try:
        return data, await async_credentials(hass, data), None
    except SecretNotFoundError:
        return {}, None, "secret_not_found"


def _account(data: Mapping[str, Any]) -> str:
    return data.get(CONF_USERNAME) or f"!secret {data.get(CONF_USERNAME_SECRET, '')}"


class EducartableConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Educartable."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            secret, resolved, error = await credentials(self.hass, user_input)
            info = None
            if resolved is not None:
                info, error = await validate(self.hass, *resolved, user_input.get(CONF_TOTP))
            if info is not None:
                await self.async_set_unique_id(str(info.get("id")))
                self._abort_if_unique_id_configured()
                name = info.get("name") or info.get("firstname") or ""
                return self.async_create_entry(title=f"Educartable · {name}" if name else "Educartable", data=secret)
            errors["base"] = error or "cannot_connect"
        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(credential_fields(user_input or {})), errors=errors
        )

    async def _check(self, entry: ConfigEntry, username: str, password: str, totp: str | None) -> str | None:
        info, error = await validate(self.hass, username, password, totp)
        if info is None:
            return error or "cannot_connect"
        if entry.unique_id and entry.unique_id != str(info.get("id")):
            return "wrong_account"
        return None

    def _update_and_abort(self, entry: ConfigEntry, data: Mapping[str, Any], reason: str) -> ConfigFlowResult:
        loaded = entry.state is ConfigEntryState.LOADED
        changed = self.hass.config_entries.async_update_entry(entry, data=dict(data))
        if not (loaded and changed):
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        return self.async_abort(reason=reason)

    @staticmethod
    def _new_data(entry: ConfigEntry, part: Mapping[str, str], keys: tuple[str, ...]) -> dict[str, Any]:
        return {**{k: v for k, v in entry.data.items() if k not in keys}, **part}

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            part, resolved, error = await credentials(self.hass, {**entry.data, **user_input})
            if resolved is not None:
                error = await self._check(entry, *resolved, user_input.get(CONF_TOTP))
            if error == "wrong_account":
                return self.async_abort(reason="wrong_account")
            if resolved is not None and error is None:
                data = self._new_data(
                    entry, part, (CONF_USERNAME, CONF_USERNAME_SECRET, CONF_PASSWORD, CONF_PASSWORD_SECRET)
                )
                return self._update_and_abort(entry, data, "reauth_successful")
            errors["base"] = error or "cannot_connect"
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(credential_fields(entry.data)),
            errors=errors,
            description_placeholders={"username": _account(entry.data)},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EducartableOptionsFlow()


class EducartableOptionsFlow(OptionsFlow):
    """Polling interval and homework window."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=clean_options(user_input))
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL, max=360, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(
                    CONF_HOMEWORK_DAYS, default=options.get(CONF_HOMEWORK_DAYS, DEFAULT_HOMEWORK_DAYS)
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="d", mode=NumberSelectorMode.BOX)
                ),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


def clean_options(options: dict[str, Any]) -> dict[str, Any]:
    return {
        CONF_SCAN_INTERVAL: max(MIN_SCAN_INTERVAL, int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))),
        CONF_HOMEWORK_DAYS: min(60, max(1, int(options.get(CONF_HOMEWORK_DAYS, DEFAULT_HOMEWORK_DAYS)))),
    }
