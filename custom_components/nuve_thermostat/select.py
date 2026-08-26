from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import NuveApi
from .const import (
    CONF_API_URL,
    CONF_CONTRACTOR_BRAND,
    CONF_CONTRACTOR_NAME,
    CONF_DEVICE_SN,
    CONF_EMAIL,
    CONF_PASSWORD,
    DOMAIN,
    SCAN_INTERVAL as POLL_SECONDS,
)

_LOGGER = logging.getLogger(__name__)

# The Nuve API uses the fan setting index. The app presents these as Auto,
# 10..50 minutes per hour, and Always on.
FAN_SETTINGS = {
    "Auto": (0, 0),
    "10 min": (1, 10),
    "20 min": (1, 20),
    "30 min": (1, 30),
    "40 min": (1, 40),
    "50 min": (1, 50),
    "Always on": (2, 60),
}
FAN_OPTIONS = tuple(FAN_SETTINGS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    api = NuveApi(entry.data[CONF_API_URL], async_get_clientsession(hass))
    await api.login(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    sn = entry.data[CONF_DEVICE_SN]

    async def update() -> Any:
        data = await api.get_fan(sn)
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            return data["data"]
        return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Nuve fan {sn}",
        update_method=update,
        update_interval=timedelta(seconds=POLL_SECONDS),
    )
    await coordinator.async_config_entry_first_refresh()
    async_add_entities(
        [
            NuveFanScheduleSelect(
                coordinator,
                api,
                sn,
                entry.data.get(CONF_CONTRACTOR_NAME, ""),
                entry.data.get(CONF_CONTRACTOR_BRAND, ""),
            )
        ]
    )


class NuveFanScheduleSelect(CoordinatorEntity, SelectEntity):
    _attr_name = "Fan circulation"
    _attr_options = list(FAN_OPTIONS)

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        api: NuveApi,
        sn: str,
        contractor_name: str = "",
        contractor_brand: str = "",
    ) -> None:
        super().__init__(coordinator)
        self.api = api
        self.sn = sn
        self._attr_unique_id = f"nuve_{sn}_fan_circulation"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, sn)},
            "name": f"Nuve Thermostat {sn}",
            "manufacturer": contractor_name or "Nuve Controls LLC",
            "model": contractor_brand or "Nuve HVAC thermostat",
        }

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        mode = data.get("mode")
        minutes = data.get("workingPerHour")
        try:
            mode = int(mode)
            minutes = int(minutes or 0)
        except (TypeError, ValueError):
            return None
        if mode == 0:
            return "Auto"
        if mode == 2 or minutes >= 60:
            return "Always on"
        option = f"{minutes} min"
        return option if option in FAN_SETTINGS else None

    async def async_select_option(self, option: str) -> None:
        if option not in FAN_SETTINGS:
            raise ValueError(f"Unsupported fan circulation option: {option}")
        mode, minutes = FAN_SETTINGS[option]
        await self.api.set_fan(self.sn, mode, minutes)
        await self.coordinator.async_request_refresh()
