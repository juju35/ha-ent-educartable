"""Fixtures for Educartable tests."""

from unittest.mock import patch

import pytest
from homeassistant.components import http


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


@pytest.fixture(autouse=True)
def stub_frontend():
    """The real frontend needs the hass_frontend package, which tests don't install."""
    with (
        patch("homeassistant.components.frontend.async_setup", return_value=True),
        patch("custom_components.educartable.add_extra_js_url") as add_js,
    ):
        # No test needs a listening server (hass_client has its own); before 2026.10, starting it with
        # sockets blocked leaves a delayed config write behind. 2026.10 no longer saves that config.
        if hasattr(http, "start_http_server_and_save_config"):
            with patch.object(http, "start_http_server_and_save_config"):
                yield add_js
        else:
            yield add_js
