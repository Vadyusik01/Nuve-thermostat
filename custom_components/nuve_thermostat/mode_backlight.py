from __future__ import annotations

from typing import Any

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN

STORE_VERSION = 2
# hue = режим; value = яркость (idle тусклее, active ярче)
DEFAULT_MODE_VALUES = {
    "cool": {"hue": 210.0, "saturation": 100.0, "value": 40.0, "shadeIndex": 40.0},
    "cool_active": {"hue": 210.0, "saturation": 100.0, "value": 100.0, "shadeIndex": 100.0},
    "heat": {"hue": 15.0, "saturation": 100.0, "value": 40.0, "shadeIndex": 40.0},
    "heat_active": {"hue": 15.0, "saturation": 100.0, "value": 100.0, "shadeIndex": 100.0},
    "auto": {"hue": 180.0, "saturation": 45.0, "value": 80.0, "shadeIndex": 50.0},
    "off": {"hue": 0.0, "saturation": 0.0, "value": 25.0, "shadeIndex": 0.0},
    "aux": {"hue": 30.0, "saturation": 100.0, "value": 100.0, "shadeIndex": 100.0},
    "fan": {"hue": 120.0, "saturation": 80.0, "value": 70.0, "shadeIndex": 70.0},
    "vacation": {"hue": 180.0, "saturation": 60.0, "value": 70.0, "shadeIndex": 50.0},
}

MODE_LABELS = {
    "cool": "Cooling (idle) color",
    "cool_active": "Cooling (active) color",
    "heat": "Heating (idle) color",
    "heat_active": "Heating (active) color",
    "auto": "Auto color",
    "off": "Off color",
    "aux": "Auxiliary heat color",
    "fan": "Ventilation color",
    "vacation": "Vacation color",
}


def _stage_active(climate_data: dict[str, Any], field: str) -> bool:
    try:
        return int(climate_data.get(field, 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def _fan_active(climate_data: dict[str, Any]) -> bool:
    try:
        return int(climate_data.get("current_fan_status", 0) or 0) > 0
    except (TypeError, ValueError):
        return str(climate_data.get("current_fan_status", "")).lower() in (
            "on",
            "true",
            "active",
            "running",
        )


def mode_key(climate_data: dict[str, Any], hvac_mode: HVACMode, preset_mode=None) -> str:
    """Automatic backlight palette key.

    Priority (user rules):
    1) Active equipment stages — bright cool/heat/aux (identify real work)
    2) Fan / recirculation — overrides *idle* heat/cool (fan runs during those modes)
    3) Vacation — only while idle (no active cool/heat/aux stage)
    4) Selected HVAC mode — dim cool/heat when idle, auto, off
    """
    # 1) Actual running stages (bright)
    if _stage_active(climate_data, "current_aux_stage"):
        return "aux"
    if _stage_active(climate_data, "current_cooling_stage"):
        return "cool_active"
    if _stage_active(climate_data, "current_heating_stage"):
        return "heat_active"

    # 2) Fan recirculation beats idle heat/cool/auto
    if _fan_active(climate_data):
        return "fan"

    # 3) Vacation only when system is idle (no active stages, no fan above)
    if preset_mode == "vacation":
        return "vacation"

    # 4) Selected mode (dim idle colours for heat/cool)
    if hvac_mode == HVACMode.COOL:
        return "cool"
    if hvac_mode == HVACMode.HEAT:
        return "heat"
    if hvac_mode == HVACMode.AUTO:
        return "auto"
    if hvac_mode == HVACMode.FAN_ONLY:
        return "fan"
    return "off"



def mode_settings(hass: HomeAssistant, domain: str, entry_id: str) -> dict[str, Any]:
    entry_data = hass.data.setdefault(domain, {}).setdefault(entry_id, {})
    settings = entry_data.setdefault("mode_backlight", {})
    settings.setdefault("enabled", False)
    modes = settings.setdefault("modes", {})
    for key, default in DEFAULT_MODE_VALUES.items():
        current = modes.setdefault(key, {})
        for field, value in default.items():
            current.setdefault(field, value)
    return settings


async def async_load_mode_settings(hass: HomeAssistant, entry) -> dict[str, Any]:
    settings = mode_settings(hass, DOMAIN, entry.entry_id)
    store = Store(hass, STORE_VERSION, f"{DOMAIN}.{entry.entry_id}.mode_backlight")
    settings["store"] = store
    try:
        saved = await store.async_load()
    except Exception:
        saved = None
    if isinstance(saved, dict):
        if isinstance(saved.get("enabled"), bool):
            settings["enabled"] = saved["enabled"]
        saved_modes = saved.get("modes")
        if isinstance(saved_modes, dict):
            for mode, values in saved_modes.items():
                if mode in settings["modes"] and isinstance(values, dict):
                    for field in ("hue", "saturation", "value", "shadeIndex"):
                        if isinstance(values.get(field), (int, float)):
                            settings["modes"][mode][field] = float(values[field])
    return settings


async def async_save_mode_settings(settings: dict[str, Any]) -> None:
    store = settings.get("store")
    if store is None:
        return
    await store.async_save(
        {
            "enabled": bool(settings.get("enabled", False)),
            "modes": {
                mode: {
                    field: float(values[field])
                    for field in ("hue", "saturation", "value", "shadeIndex")
                }
                for mode, values in settings.get("modes", {}).items()
                if isinstance(values, dict)
            },
        }
    )


async def async_reset_mode_settings_to_defaults(settings: dict[str, Any]) -> None:
    """Replace palette with code defaults (ignores old store values)."""
    modes = settings.setdefault("modes", {})
    for key, default in DEFAULT_MODE_VALUES.items():
        modes[key] = dict(default)
    settings.pop("last_applied", None)
    await async_save_mode_settings(settings)
