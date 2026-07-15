"""Config flow for the Hidraqua (Veolia España) integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import Hidraqua2FAError, HidraquaAuthError, HidraquaClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class HidraquaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hidraqua."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            session = async_create_clientsession(self.hass)
            client = HidraquaClient(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD], session
            )
            try:
                await client.async_login()
            except HidraquaAuthError:
                errors["base"] = "invalid_auth"
            except Hidraqua2FAError:
                errors["base"] = "two_factor_not_supported"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Error inesperado validando credenciales")
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
