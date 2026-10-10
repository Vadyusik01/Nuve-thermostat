from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import NuveApi
from .runtime import async_get_runtime
_LOGGER = logging.getLogger(__name__)

from .const import (
    CONF_API_URL,
    CONF_CONTRACTOR_BRAND,
    CONF_CONTRACTOR_NAME,
    CONF_DEVICE_SN,
    CONF_EMAIL,
    CONF_PASSWORD,
    DOMAIN,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    runtime = await async_get_runtime(hass, entry)
    coordinator = runtime.status_coordinator
    sn = runtime.sn
    device_info = {
        "identifiers": {(DOMAIN, sn)},
        "name": f"Nuve Thermostat {sn}",
        "manufacturer": entry.data.get(CONF_CONTRACTOR_NAME) or "Nuve Controls LLC",
        "model": entry.data.get(CONF_CONTRACTOR_BRAND) or "Nuve HVAC thermostat",
    }
    async_add_entities(
        [
            NuveDiagnosticBinarySensor(coordinator, sn, key, name, device_info)
            for key, name in (
                ("is_device_online", "Device online"),
                ("heat_pump_emergency", "Heat pump emergency"),
                ("is_in_performance_test", "Performance test"),
                ("is_vacation", "Vacation mode"),
                ("hold_status", "Hold active"),
            )
        ]
    )
    _LOGGER.info("Nuve diagnostic binary sensors added for %s", sn)


class NuveDiagnosticBinarySensor(CoordinatorEntity, BinarySensorEntity):
    def __init__(self, coordinator, sn: str, key: str, name: str, device_info) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"nuve_{sn}_{key}"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data or {}
        if isinstance(data.get("main"), dict):
            data = data["main"]
        value = data.get(self.key)
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "online", "active")
        return bool(value)
