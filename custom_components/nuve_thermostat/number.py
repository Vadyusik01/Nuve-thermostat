from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator

from .api import NuveApi
from .backlight import backlight_values
from .runtime import async_get_runtime
from .const import (
    CONF_API_URL,
    CONF_CONTRACTOR_BRAND,
    CONF_CONTRACTOR_NAME,
    CONF_DEVICE_SN,
    CONF_EMAIL,
    CONF_PASSWORD,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    runtime = await async_get_runtime(hass, entry)
    api = runtime.api
    coordinator = runtime.backlight_coordinator
    sn = runtime.sn
    device_info = {
        "identifiers": {(DOMAIN, sn)},
        "name": f"Nuve Thermostat {sn}",
        "manufacturer": entry.data.get(CONF_CONTRACTOR_NAME) or "Nuve Controls LLC",
        "model": entry.data.get(CONF_CONTRACTOR_BRAND) or "Nuve HVAC thermostat",
    }
    entities = [
            NuveBacklightNumber(
                coordinator, api, sn, device_info,
                key="hue", name="Backlight hue", minimum=0.0, maximum=360.0,
                step=1.0, icon="mdi:palette",
            ),
            NuveBacklightNumber(
                coordinator, api, sn, device_info,
                key="value", name="Backlight brightness", minimum=0.0, maximum=100.0,
                step=1.0, icon="mdi:brightness-6",
            ),
            NuveBacklightNumber(
                coordinator, api, sn, device_info,
                key="shadeIndex", name="Backlight shade", minimum=0.0, maximum=100.0,
                step=1.0, icon="mdi:format-color-fill",
            ),
        ]
    async_add_entities(entities)


class NuveBacklightNumber(CoordinatorEntity, NumberEntity):
    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        api: NuveApi,
        sn: str,
        device_info: dict[str, Any],
        *,
        key: str,
        name: str,
        minimum: float,
        maximum: float,
        step: float,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self.api = api
        self.sn = sn
        self.key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        if key == "hue":
            self._attr_native_unit_of_measurement = "°"
        elif key == "value":
            self._attr_native_unit_of_measurement = "%"
        self._attr_unique_id = f"nuve_{sn}_backlight_{key}"
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if not isinstance(data, dict):
            return None
        try:
            return float(data[self.key])
        except (KeyError, TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        data = self.coordinator.data or {}
        sat = float(data.get("saturation", 100) or 0)
        # Colour is invisible at saturation 0 (always white)
        if self.key == "hue" and sat <= 0:
            sat = 100.0
        await self.api.set_backlight(
            self.sn,
            on=bool(data.get("on", True)),
            hue=float(value) if self.key == "hue" else float(data.get("hue", 0)),
            saturation=float(value) if self.key == "saturation" else sat,
            value=float(value) if self.key == "value" else float(data.get("value", 100)),
            shade_index=(
                float(value)
                if self.key == "shadeIndex"
                else float(data.get("shadeIndex", 0))
            ),
            value_scale=float(data.get("value_scale", 1.0)),
        )
        await self.coordinator.async_request_refresh()
