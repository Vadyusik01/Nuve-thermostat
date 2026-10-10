from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import NuveApi
from .backlight import backlight_values
from .const import (
    CONF_API_URL,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_DEVICE_SN,
    DOMAIN,
    SCAN_INTERVAL,
    FAN_SCAN_INTERVAL,
    BACKLIGHT_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class NuveRuntime:
    """Shared API client and coordinators for one config entry."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.sn = entry.data[CONF_DEVICE_SN]
        self.api = NuveApi(
            entry.data[CONF_API_URL],
            async_get_clientsession(hass),
        )
        self._static_info: dict[str, Any] = {}
        self.status_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"Nuve status {self.sn}",
            update_method=self._update_status,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.fan_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"Nuve fan {self.sn}",
            update_method=self._update_fan,
            update_interval=timedelta(seconds=FAN_SCAN_INTERVAL),
        )
        self.backlight_coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"Nuve backlight {self.sn}",
            update_method=self._update_backlight,
            update_interval=timedelta(seconds=BACKLIGHT_SCAN_INTERVAL),
        )
        self._initialized = False

    async def async_initialize(self) -> None:
        if self._initialized:
            return
        await self.api.login(
            self.entry.data[CONF_EMAIL],
            self.entry.data[CONF_PASSWORD],
        )
        try:
            static_info = await self.api.get_static_info(self.sn)
            if isinstance(static_info, dict) and isinstance(
                static_info.get("data"), dict
            ):
                static_info = static_info["data"]
            if isinstance(static_info, dict):
                self._static_info = static_info
        except Exception as exc:
            _LOGGER.debug("Nuve static info unavailable: %s", exc)
        await self.status_coordinator.async_config_entry_first_refresh()
        await self.fan_coordinator.async_config_entry_first_refresh()
        await self.backlight_coordinator.async_config_entry_first_refresh()
        self._initialized = True

    async def _update_status(self) -> dict[str, Any]:
        main = await self.api.main_data(self.sn)
        if isinstance(main, dict) and isinstance(main.get("data"), dict):
            main = main["data"]
        if not isinstance(main, dict):
            main = {}
        try:
            alerts = await self.api.get_alerts(self.sn)
        except Exception as exc:
            _LOGGER.debug("Nuve alerts unavailable: %s", exc)
            alerts = {}
        return {"main": main, "static": self._static_info, "alerts": alerts}

    async def _update_fan(self) -> Any:
        data = await self.api.get_fan(self.sn)
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            return data["data"]
        return data

    async def _update_backlight(self) -> dict[str, Any]:
        return backlight_values(await self.api.get_backlight(self.sn))


async def async_get_runtime(hass: HomeAssistant, entry) -> NuveRuntime:
    entries = hass.data.setdefault(DOMAIN, {})
    container = entries.setdefault(entry.entry_id, {"entry": entry})
    runtime = container.get("runtime")
    if runtime is None:
        runtime = NuveRuntime(hass, entry)
        container["runtime"] = runtime
        await runtime.async_initialize()
    return runtime
