"""The Hidraqua (Veolia España) integration."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HidraquaApiError, HidraquaAuthError, HidraquaClient
from .const import DOMAIN, PLATFORMS
from .statistics import async_import_hourly_statistics

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=12)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hidraqua from a config entry."""
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    # Sesión propia con cookies aisladas por integración (necesario porque
    # el portal identifica la sesión/contrato vía cookies, no por token).
    session = async_create_clientsession(hass)
    client = HidraquaClient(username, password, session)

    coordinator = HidraquaDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Primer intento de backfill horario: en el ciclo de
    # async_config_entry_first_refresh() de arriba, la entidad
    # "última lectura" todavía no existía (se crea justo en la línea
    # anterior), así que ese primer intento se salta en silencio. Lo
    # relanzamos ahora que las entidades ya están registradas.
    hass.async_create_background_task(
        coordinator._async_import_hourly_stats_safe(),
        name="hidraqua_initial_hourly_stats",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


class HidraquaDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from the Hidraqua portal."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: HidraquaClient
    ) -> None:
        self.api = client
        self._entry = entry
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL
        )

    async def _async_update_data(self):
        try:
            data = await self.api.async_update_all()
        except HidraquaAuthError as err:
            raise ConfigEntryNotReady(
                "Credenciales de Hidraqua rechazadas"
            ) from err
        except HidraquaApiError as err:
            raise UpdateFailed(f"Error consultando Hidraqua: {err}") from err

        # El backfill horario puede implicar muchas peticiones paginadas
        # (hasta ~36 solo para 30 días). Lo lanzamos en segundo plano para no
        # bloquear ni el arranque de HA ni las actualizaciones de los
        # sensores principales, que solo dependen del consumo diario.
        self.hass.async_create_background_task(
            self._async_import_hourly_stats_safe(),
            name="hidraqua_hourly_stats_import",
        )

        return data

    async def _async_import_hourly_stats_safe(self) -> None:
        """Wrapper que nunca deja escapar una excepción de la tarea en segundo plano."""
        try:
            await async_import_hourly_statistics(self.hass, self._entry, self.api)
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Error importando estadísticas horarias de Hidraqua")
