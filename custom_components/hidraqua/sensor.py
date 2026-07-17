"""Sensor platform for the Hidraqua (Veolia España) integration."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HidraquaDataUpdateCoordinator
from .const import (
    DAILY_CONSUMPTION_UNIQUE_ID_SUFFIX,
    DOMAIN,
    LAST_READING_UNIQUE_ID_SUFFIX,
    MANUFACTURER,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Hidraqua sensors from a config entry."""
    coordinator: HidraquaDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            HidraquaDailyConsumptionSensor(coordinator, entry),
            HidraquaLastReadingSensor(coordinator, entry),
        ]
    )


class HidraquaBaseSensor(CoordinatorEntity, SensorEntity):
    """Base entity sharing device info between Hidraqua sensors."""

    def __init__(
        self, coordinator: HidraquaDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer=MANUFACTURER,
            model="Contador de agua",
        )


class HidraquaDailyConsumptionSensor(HidraquaBaseSensor):
    """Daily water consumption in m³ (valor informativo, se reinicia cada día)."""

    _attr_has_entity_name = True
    _attr_translation_key = "daily_consumption"
    # Sin device_class: Home Assistant solo permite device_class "water"
    # junto a state_class "total"/"total_increasing"/None, nunca con
    # "measurement". Como este valor SÍ es un measurement (se reinicia cada
    # día, no es un totalizador), dejamos device_class sin especificar y
    # ponemos el icono a mano. La entidad con device_class water de verdad
    # es "Última lectura".
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "m³"
    _attr_icon = "mdi:water"

    def __init__(
        self, coordinator: HidraquaDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{DAILY_CONSUMPTION_UNIQUE_ID_SUFFIX}"

    @property
    def native_value(self):
        return self.coordinator.data.get("daily_consumption")

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        return {
            "last_reading_date": data.get("last_reading_date"),
            "consumption_type": data.get("consumption_type"),
            "historyConsumption": data.get("history_consumption"),
        }


class HidraquaLastReadingSensor(HidraquaBaseSensor):
    """Absolute meter reading in m³.

    Esta es la entidad recomendada como fuente de "Agua" en el dashboard de
    Energía: es el totalizador real del contador, y además recibe el
    histórico horario importado por statistics.py, así que el panel de
    Energía puede pintar consumo por horas, no solo por ciclo de 12h.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "last_reading"
    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "m³"
    _attr_icon = "mdi:gauge"

    def __init__(
        self, coordinator: HidraquaDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{LAST_READING_UNIQUE_ID_SUFFIX}"

    @property
    def native_value(self):
        return self.coordinator.data.get("last_reading")

    @property
    def extra_state_attributes(self):
        return {
            "last_reading_date": self.coordinator.data.get("last_reading_date"),
        }
