"""Import hourly Hidraqua consumption into the 'last reading' sensor statistics.

En vez de crear una fuente de estadísticas externa suelta (que no aparece
como opción seleccionable en el dashboard de Energía), este módulo inyecta
el histórico horario directamente en las estadísticas de la propia entidad
sensor.hidraqua_ultima_lectura. El dashboard de Energía siempre lee de la
tabla de estadísticas de la entidad seleccionada, así que en cuanto esa
entidad tiene puntos horarios, el panel "Agua" los pinta automáticamente.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import StatisticData, StatisticMetaData
from homeassistant.components.recorder.statistics import (
    async_import_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from .api import HidraquaApiError, HidraquaClient
from .const import DOMAIN, LAST_READING_UNIQUE_ID_SUFFIX

_LOGGER = logging.getLogger(__name__)

# Al añadir la integración por primera vez no cargamos el año entero de golpe
# (serían ~8760 llamadas paginadas): empezamos con un mes y desde ahí el
# import es incremental en cada ciclo del coordinador.
INITIAL_BACKFILL_DAYS = 30

try:
    # Disponible desde HA 2024.x aprox.; en versiones futuras (2026.11+)
    # sustituye por completo al antiguo booleano has_mean.
    from homeassistant.components.recorder.statistics import StatisticMeanType

    _HAS_MEAN_TYPE = True
except ImportError:
    _HAS_MEAN_TYPE = False


def _find_last_reading_entity_id(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """Look up the real entity_id of the 'última lectura' sensor."""
    unique_id = f"{entry.entry_id}_{LAST_READING_UNIQUE_ID_SUFFIX}"
    registry = er.async_get(hass)
    return registry.async_get_entity_id("sensor", DOMAIN, unique_id)


async def async_import_hourly_statistics(
    hass: HomeAssistant, entry: ConfigEntry, client: HidraquaClient
) -> None:
    """Fetch new hourly readings and backfill them into the sensor's statistics."""
    entity_id = _find_last_reading_entity_id(hass, entry)
    if entity_id is None:
        # Ocurre en el primerísimo ciclo, antes de que sensor.py haya
        # registrado la entidad. __init__.py relanza este import justo
        # después de montar las plataformas, así que no es un problema.
        _LOGGER.debug(
            "Import horario: la entidad 'última lectura' todavía no existe, "
            "se reintentará en el próximo ciclo"
        )
        return

    _LOGGER.debug("Import horario: iniciando para %s", entity_id)

    last_stats = await get_instance(hass).async_add_executor_job(
        get_last_statistics, hass, 1, entity_id, True, {"sum"}
    )

    threshold_utc = None
    if last_stats.get(entity_id):
        last_entry = last_stats[entity_id][0]
        threshold_utc = dt_util.utc_from_timestamp(last_entry["start"])
        fecha_inicio = dt_util.as_local(threshold_utc).date()
    else:
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

        # "reading" es el totalizador absoluto del contador (m³): al ser ya
        # de por sí un acumulado creciente, lo usamos tal cual tanto como
        # estado de esa hora como como suma, igual que hace la propia
        # entidad con su valor en vivo.
        statistics.append(
            StatisticData(
                start=start_utc,
                state=record["reading"],
                sum=record["reading"],
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

    metadata_kwargs = dict(
        has_mean=False,  # deprecado, se mantiene por compatibilidad con HA < 2026.x
        has_sum=True,
        name=None,  # con statistic_id == entity_id, HA usa el nombre de la entidad
        source="recorder",
        statistic_id=entity_id,
        unit_of_measurement="m³",
    )
    if _HAS_MEAN_TYPE:
        metadata_kwargs["mean_type"] = StatisticMeanType.NONE

    metadata = StatisticMetaData(**metadata_kwargs)

    async_import_statistics(hass, metadata, statistics)
    _LOGGER.debug(
        "Importados %d puntos horarios de consumo en %s",
        len(statistics),
        entity_id,
    )
