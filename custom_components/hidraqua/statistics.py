"""Import hourly Hidraqua consumption into Home Assistant's long-term statistics."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .api import HidraquaApiError, HidraquaClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Al añadir la integración por primera vez no cargamos el año entero de golpe
# (serían ~8760 llamadas paginadas): empezamos con un mes y desde ahí el
# import es incremental en cada ciclo del coordinador.
INITIAL_BACKFILL_DAYS = 30


def _statistic_id(entry: ConfigEntry) -> str:
    return f"{DOMAIN}:consumo_horario_{entry.entry_id.lower()}"


async def async_import_hourly_statistics(
    hass: HomeAssistant, entry: ConfigEntry, client: HidraquaClient
) -> None:
    """Fetch new hourly consumption records and feed the recorder statistics."""
    statistic_id = _statistic_id(entry)
    _LOGGER.debug("Import horario: iniciando para %s", statistic_id)

    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, statistic_id, True, {"sum"}
    )

    threshold_utc = None
    if last_stats.get(statistic_id):
        last_entry = last_stats[statistic_id][0]
        running_sum = last_entry["sum"] or 0.0
        threshold_utc = dt_util.utc_from_timestamp(last_entry["start"])
        fecha_inicio = dt_util.as_local(threshold_utc).date()
    else:
        running_sum = 0.0
        fecha_inicio = date.today() - timedelta(days=INITIAL_BACKFILL_DAYS)

    fecha_fin = date.today()
    _LOGGER.debug(
        "Import horario: rango %s -> %s (threshold_utc=%s)",
        fecha_inicio,
        fecha_fin,
        threshold_utc,
    )
    if fecha_inicio > fecha_fin:
        _LOGGER.debug("Import horario: nada que traer, ya está al día")
        return

    try:
        records = await client.async_get_hourly_consumption(fecha_inicio, fecha_fin)
    except HidraquaApiError as err:
        _LOGGER.warning("No se pudieron importar estadísticas horarias: %s", err)
        return

    _LOGGER.debug("Import horario: %d registros recibidos del portal", len(records))

    if not records:
        _LOGGER.debug("Import horario: el portal devolvió una lista vacía")
        return

    local_tz = dt_util.get_time_zone(hass.config.time_zone) or dt_util.DEFAULT_TIME_ZONE

    statistics: list[StatisticData] = []
    for record in records:
        local_dt = record["start"].replace(
            minute=0, second=0, microsecond=0, tzinfo=local_tz
        )
        start_utc = dt_util.as_utc(local_dt)

        if threshold_utc is not None and start_utc <= threshold_utc:
            continue  # ya importado en un ciclo anterior

        running_sum += record["consumption"]
        statistics.append(
            StatisticData(
                start=start_utc,
                state=record["consumption"],
                sum=round(running_sum, 3),
            )
        )

    if not statistics:
        _LOGGER.debug(
            "Import horario: %d registros recibidos pero todos ya importados "
            "(threshold_utc=%s)",
            len(records),
            threshold_utc,
        )
        return

    metadata = StatisticMetaData(
        has_mean=False,
        has_sum=True,
        name=f"{entry.title} consumo horario",
        source=DOMAIN,
        statistic_id=statistic_id,
        unit_of_measurement="m³",
    )

    async_add_external_statistics(hass, metadata, statistics)
    _LOGGER.debug(
        "Importados %d puntos horarios de consumo (%s)",
        len(statistics),
        statistic_id,
    )
