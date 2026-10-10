from __future__ import annotations

from typing import Any

from homeassistant.components.light import ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CONTRACTOR_BRAND,
    CONF_CONTRACTOR_NAME,
    CONF_DEVICE_SN,
    DOMAIN,
)
from .mode_backlight import MODE_LABELS, async_save_mode_settings, mode_settings


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> None:
    settings = mode_settings(hass, DOMAIN, entry.entry_id)
    sn = entry.data[CONF_DEVICE_SN]
    device_info = {
        "identifiers": {(DOMAIN, sn)},
        "name": f"Nuve Thermostat {sn}",
        "manufacturer": entry.data.get(CONF_CONTRACTOR_NAME) or "Nuve Controls LLC",
        "model": entry.data.get(CONF_CONTRACTOR_BRAND) or "Nuve HVAC thermostat",
    }
    async_add_entities(
        [
            NuveModeBacklightLight(settings, sn, mode, label, device_info)
            for mode, label in MODE_LABELS.items()
        ]
    )


class NuveModeBacklightLight(LightEntity):
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

    def __init__(
        self,
        settings: dict[str, Any],
        sn: str,
        mode: str,
        name: str,
        device_info: dict[str, Any],
    ) -> None:
        self.settings = settings
        self.mode = mode
        self._attr_name = name
        self._attr_unique_id = f"nuve_{sn}_{mode}_backlight_color"
        self._attr_device_info = device_info

    @property
    def _values(self) -> dict[str, float]:
        return self.settings["modes"][self.mode]

    @property
    def is_on(self) -> bool:
        return float(self._values.get("value", 0)) > 0

    @property
    def hs_color(self) -> tuple[float, float]:
        return (
            float(self._values.get("hue", 0)),
            float(self._values.get("saturation", 0)),
        )

    @property
    def brightness(self) -> int:
        return int(float(self._values.get("value", 100)) * 2.55)

    async def async_turn_on(self, **kwargs: Any) -> None:
        hs_color = kwargs.get("hs_color")
        if hs_color is not None:
            self._values["hue"] = max(0.0, min(360.0, float(hs_color[0])))
            self._values["saturation"] = max(0.0, min(100.0, float(hs_color[1])))
        brightness = kwargs.get("brightness")
        if brightness is not None:
            self._values["value"] = max(0.0, min(100.0, float(brightness) / 2.55))
        elif self._values.get("value", 0) <= 0:
            self._values["value"] = 100.0
        await async_save_mode_settings(self.settings)
        self.async_write_ha_state()
        callback = self.settings.get("apply")
        if callback:
            await callback()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._values["value"] = 0.0
        await async_save_mode_settings(self.settings)
        self.async_write_ha_state()
        callback = self.settings.get("apply")
        if callback:
            await callback()
