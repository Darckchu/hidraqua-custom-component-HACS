"""Constants for the Hidraqua (Veolia España) integration."""

DOMAIN = "hidraqua"
DEFAULT_NAME = "Hidraqua"
MANUFACTURER = "Veolia España"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

PLATFORMS = ["sensor"]

# Sufijos de unique_id compartidos entre sensor.py y statistics.py, para que
# el import de estadísticas horarias sepa a qué entidad exacta enlazar.
LAST_READING_UNIQUE_ID_SUFFIX = "last_reading"
DAILY_CONSUMPTION_UNIQUE_ID_SUFFIX = "daily_consumption"
