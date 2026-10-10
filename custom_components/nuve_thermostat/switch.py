from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import NuveApi
from .backlight import backlight_values
from .const import DOMAIN
from .mode_backlight import async_save_mode_settings, mode_settings
from .runtime import async_get_runtime
from .const import (
    CONF_API_URL,
    CONF_CONTRACTOR_BRAND,
    CONF_CONTRACTOR_NAME,
    CONF_DEVICE_SN,
    CONF_EMAIL,
    CONF_PASSWORD,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    runtime = await async_get_runtime(hass, entry)
    api = runtime.api
    coordinator = runtime.backlight_coordinator
    sn = runtime.sn
    settings = mode_settings(hass, DOMAIN, entry.entry_id)
    device_info = {
        "identifiers": {(DOMAIN, sn)},
        "name": f"Nuve Thermostat {sn}",
        "manufacturer": entry.data.get(CONF_CONTRACTOR_NAME) or "Nuve Controls LLC",
        "model": entry.data.get(CONF_CONTRACTOR_BRAND) or "Nuve HVAC thermostat",
    }
    async_add_entities(
        [
            NuveBacklightSwitch(coordinator, api, sn, device_info),
            NuveAutomaticModeBacklightSwitch(settings, sn, device_info),
        ]
    )


class NuveBacklightSwitch(CoordinatorEntity, SwitchEntity):
    _attr_name = "Backlight"
    _attr_icon = "mdi:led-on"

    def __init__(self, coordinator, api: NuveApi, sn: str, device_info) -> None:
        super().__init__(coordinator)
        self.api = api
        self.sn = sn
        self._attr_unique_id = f"nuve_{sn}_backlight"
        self._attr_device_info = device_info

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        return bool(data.get("on", True)) if isinstance(data, dict) else True

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_state(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_state(False)

    async def _set_state(self, state: bool) -> None:
        data = self.coordinator.data or {}
        await self.api.set_backlight(
            self.sn,
            on=state,
            hue=float(data.get("hue", 0)),
            saturation=float(data.get("saturation", 100)),
            value=float(data.get("value", 100)),
            shade_index=float(data.get("shadeIndex", 0)),
            value_scale=float(data.get("value_scale", 1.0)),
        )
        await self.coordinator.async_request_refresh()


class NuveAutomaticModeBacklightSwitch(RestoreEntity, SwitchEntity):
    _attr_name = "Automatic mode backlight"
    _attr_icon = "mdi:theme-light-dark"

    def __init__(self, settings: dict[str, Any], sn: str, device_info) -> None:
        self.settings = settings
        self._attr_unique_id = f"nuve_{sn}_automatic_mode_backlight"
        self._attr_device_info = device_info

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            self.settings["enabled"] = last_state.state == "on"
        callback = self.settings.get("apply")
        if callback and self.settings.get("enabled"):
            await callback()

    @property
    def is_on(self) -> bool:
        return bool(self.settings.get("enabled", False))

    async def async_turn_on(self, **kwargs) -> None:
        self.settings["enabled"] = True
        await async_save_mode_settings(self.settings)
        self.async_write_ha_state()
        callback = self.settings.get("apply")
        if callback:
            await callback()

    async def async_turn_off(self, **kwargs) -> None:
        self.settings["enabled"] = False
        await async_save_mode_settings(self.settings)
        self.async_write_ha_state()
