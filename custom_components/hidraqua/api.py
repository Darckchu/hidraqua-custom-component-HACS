"""API client for the Hidraqua (Veolia Spain / Liferay DXP) customer portal."""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://hidraqua.veolia.es"
LOGIN_PATH = "/login"
CONSUMPTION_PATH = "/es/group/hidraqua/mis-consumos"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "HomeAssistantHidraquaIntegration/1.0"
)

P_AUTH_RE = re.compile(r"p_auth=([a-zA-Z0-9]+)")


class HidraquaApiError(Exception):
    """Generic API error."""


class HidraquaAuthError(HidraquaApiError):
    """Raised when credentials are rejected."""


class Hidraqua2FAError(HidraquaApiError):
    """Raised when the account has 2FA enabled (not supported)."""


class HidraquaClient:
    """Async client for the Hidraqua / Veolia España customer portal."""

    def __init__(
        self, username: str, password: str, session: aiohttp.ClientSession
    ) -> None:
        self._username = username
        self._password = password
        self._session = session
        self._logged_in = False

    async def _get_p_auth(self, referer_path: str) -> str:
        """Load a page and extract the current Liferay CSRF (p_auth) token."""
        async with self._session.get(
            f"{BASE_URL}{referer_path}",
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            resp.raise_for_status()
            text = await resp.text()

        match = P_AUTH_RE.search(text)
        if not match:
            raise HidraquaApiError(f"No se encontró p_auth en {referer_path}")
        return match.group(1)

    async def async_login(self) -> bool:
        """Authenticate against the portal. Returns True on success."""
        p_auth = await self._get_p_auth(LOGIN_PATH)

        check_params = {
            "p_p_id": "CustomLoginPortlet",
            "p_p_lifecycle": "2",
            "p_p_state": "normal",
            "p_p_mode": "view",
            "p_p_resource_id": "/checkDoubleFactor",
            "p_p_cacheability": "cacheLevelPage",
            "p_auth": p_auth,
            "_CustomLoginPortlet_login": self._username,
            "_CustomLoginPortlet_password": self._password,
        }
        async with self._session.get(
            f"{BASE_URL}{LOGIN_PATH}",
            params=check_params,
            headers={"User-Agent": USER_AGENT},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

        if data.get("hasError"):
            raise HidraquaAuthError("Usuario o contraseña incorrectos")
        if data.get("is2FAActive"):
            raise Hidraqua2FAError(
                "La cuenta tiene doble factor activado, no soportado"
            )

        login_params = {
            "p_p_id": "CustomLoginPortlet",
            "p_p_lifecycle": "1",
            "p_p_state": "normal",
            "p_p_mode": "view",
            "_CustomLoginPortlet_javax.portlet.action": "/login/login",
            "_CustomLoginPortlet_mvcRenderCommandName": "/login/login",
            "p_auth": p_auth,
        }
        login_data = {
            "saveLastPath": "false",
            "redirect": "",
            "doActionAfterLogin": "false",
            "_CustomLoginPortlet_login": self._username,
            "_CustomLoginPortlet_password": self._password,
        }
        async with self._session.post(
            f"{BASE_URL}{LOGIN_PATH}",
            params=login_params,
            data=login_data,
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True,
        ) as resp:
            resp.raise_for_status()

        cookie_names = {
            c.key for c in self._session.cookie_jar.filter_cookies(BASE_URL).values()
        }
        self._logged_in = "ID" in cookie_names
        if not self._logged_in:
            raise HidraquaAuthError("El login no generó una sesión válida")
        return True

    async def async_get_daily_consumption(
        self, fecha_inicio: date, fecha_fin: date
    ) -> list[dict[str, Any]]:
        """Return the daily consumption records between two dates."""
        if not self._logged_in:
            await self.async_login()

        p_auth = await self._get_p_auth(CONSUMPTION_PATH)

        all_consumos: list[dict[str, Any]] = []
        inicio, tam_pagina = 0, 20

        while True:
            params = {
                "p_p_id": "MisConsumos",
                "p_p_lifecycle": "2",
                "p_p_state": "normal",
                "p_p_mode": "view",
                "p_p_cacheability": "cacheLevelPage",
                "p_auth": p_auth,
                "_MisConsumos_op": "buscarConsumosDiaria",
                "_MisConsumos_fechaInicio": fecha_inicio.strftime("%d/%m/%Y"),
                "_MisConsumos_fechaFin": fecha_fin.strftime("%d/%m/%Y"),
                "_MisConsumos_inicio": str(inicio),
                "_MisConsumos_fin": str(inicio + tam_pagina - 1),
            }
            async with self._session.get(
                f"{BASE_URL}{CONSUMPTION_PATH}",
                params=params,
                headers={"User-Agent": USER_AGENT},
            ) as resp:
                if resp.status != 200:
                    raise HidraquaApiError(
                        f"Error {resp.status} obteniendo consumo"
                    )
                data = await resp.json(content_type=None)

            if not isinstance(data, dict) or "consumos" not in data:
                # Sesión caducada u otra respuesta inesperada (p.ej. HTML de login)
                self._logged_in = False
                raise HidraquaApiError(
                    "Respuesta inesperada del portal (¿sesión caducada?)"
                )

            all_consumos.extend(data.get("consumos", []))

            if data.get("ultimaPagina", True):
                break
            inicio += tam_pagina

        return all_consumos

    async def async_update_all(self) -> dict[str, Any]:
        """Fetch a rolling window of consumption data for the coordinator."""
        fecha_fin = date.today()
        fecha_inicio = fecha_fin - timedelta(days=45)

        try:
            consumos = await self.async_get_daily_consumption(fecha_inicio, fecha_fin)
        except HidraquaApiError:
            # Reintenta una vez forzando un nuevo login por si la sesión caducó
            self._logged_in = False
            await self.async_login()
            consumos = await self.async_get_daily_consumption(fecha_inicio, fecha_fin)

        if not consumos:
            raise HidraquaApiError("El portal no devolvió datos de consumo")

        # El portal los devuelve del más reciente al más antiguo
        latest = consumos[0]

        def _to_float(value: str) -> float:
            return float(str(value).replace(",", "."))

        history = [
            [c["fechaConsumo"], _to_float(c["consumo"])] for c in consumos
        ]

        return {
            "last_reading": _to_float(latest["lectura"]),
            "last_reading_date": latest["fechaConsumo"],
            "daily_consumption": _to_float(latest["consumo"]),
            "consumption_type": latest.get("consumptionType", {}).get(
                "consumptionLiteral"
            ),
            "history_consumption": history,
        }
