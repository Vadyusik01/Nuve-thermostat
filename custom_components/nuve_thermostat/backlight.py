from __future__ import annotations

from typing import Any


def unwrap_backlight(data: Any) -> dict[str, Any]:
    """Normalize the API response to a backlight dictionary."""
    if isinstance(data, dict):
        nested = data.get("data")
        if isinstance(nested, dict):
            return nested
        return data
    return {}


def as_float(data: dict[str, Any], *keys: str, default: float) -> float:
    for key in keys:
        value = data.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return default


def as_bool(data: dict[str, Any], *keys: str, default: bool) -> bool:
    for key in keys:
        value = data.get(key)
        if value is not None:
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("1", "true", "on", "yes")
            return bool(value)
    return default


def backlight_values(data: Any) -> dict[str, Any]:
    """Return stable HA-friendly values from either known API response shape."""
    normalized = unwrap_backlight(data)
    raw_value = as_float(normalized, "value", "brightness", default=100.0)
    value_scale = 1.0 if 0.0 <= raw_value <= 1.0 else 100.0
    value = raw_value * 100.0 if value_scale == 1.0 else raw_value

    raw_saturation = as_float(normalized, "saturation", default=100.0)
    saturation = raw_saturation * 100.0 if 0.0 <= raw_saturation <= 1.0 else raw_saturation

    raw_hue = as_float(normalized, "hue", default=0.0)
    # API returns hue 0..1; HA number entity uses degrees 0..360
    hue = raw_hue * 360.0 if 0.0 <= raw_hue <= 1.0 else raw_hue

    # shadeIndex: pass through (do not rescale; device-specific)
    shade = as_float(normalized, "shadeIndex", "shade_index", default=0.0)

    return {
        "on": as_bool(normalized, "isOn", "on", "state", default=True),
        "hue": hue,
        "saturation": saturation,
        "value": value,
        "value_scale": value_scale,
        "shadeIndex": shade,
    }
