"""Pure equipment-activity and runtime accounting logic.

No Home Assistant imports here: this module is unit-testable on its own.
The HA-facing wrappers live in sensor.py (Store persistence, entities)
and climate.py (hvac_action).
"""
from __future__ import annotations

from typing import Any

# Activity values, also used as the enum options of the activity sensor.
ACTIVITY_AUX_HEAT = "aux_heat"
ACTIVITY_COOLING = "cooling"
ACTIVITY_HEATING = "heating"
ACTIVITY_FAN = "fan"
ACTIVITY_IDLE = "idle"
ACTIVITY_OFF = "off"

ACTIVITY_OPTIONS = [
    ACTIVITY_HEATING,
    ACTIVITY_COOLING,
    ACTIVITY_AUX_HEAT,
    ACTIVITY_FAN,
    ACTIVITY_IDLE,
    ACTIVITY_OFF,
]

# Runtime channels. "fan" means fan circulation only (fan running with no
# heating/cooling/aux stage) — the periodic ventilation the user schedules.
RUNTIME_CHANNELS = ("heating", "cooling", "aux", "fan")


def stage_active(main: dict[str, Any], field: str) -> bool:
    try:
        return int(main.get(field, 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def fan_active(main: dict[str, Any]) -> bool:
    try:
        return int(main.get("current_fan_status", 0) or 0) > 0
    except (TypeError, ValueError):
        return str(main.get("current_fan_status", "")).lower() in (
            "on",
            "true",
            "active",
            "running",
        )


def _is_off(main: dict[str, Any]) -> bool:
    alias = main.get("mode_alias")
    if alias is not None:
        return str(alias).lower().strip() == "off"
    try:
        # API mode ids: 0 and 5 are Off (see climate.MODE_MAP).
        return int(main.get("mode", -1)) in (0, 5)
    except (TypeError, ValueError):
        return False


def current_activity(main: dict[str, Any] | None) -> str | None:
    """What the equipment is actually doing right now.

    Priority mirrors the automatic-backlight rules: a running stage beats
    fan circulation, fan circulation beats idle. Returns None when there
    is no data at all.
    """
    if not main:
        return None
    if stage_active(main, "current_aux_stage"):
        return ACTIVITY_AUX_HEAT
    if stage_active(main, "current_cooling_stage"):
        return ACTIVITY_COOLING
    if stage_active(main, "current_heating_stage"):
        return ACTIVITY_HEATING
    if fan_active(main):
        return ACTIVITY_FAN
    if _is_off(main):
        return ACTIVITY_OFF
    return ACTIVITY_IDLE


def active_channels(main: dict[str, Any]) -> set[str]:
    """Runtime channels to credit for the elapsed interval."""
    channels: set[str] = set()
    if stage_active(main, "current_heating_stage"):
        channels.add("heating")
    if stage_active(main, "current_cooling_stage"):
        channels.add("cooling")
    if stage_active(main, "current_aux_stage"):
        channels.add("aux")
    # Fan counts only as standalone circulation, not while a stage runs.
    if not channels and fan_active(main):
        channels.add("fan")
    return channels


class RuntimeCounters:
    """Accumulated equipment runtime: totals plus per-day counters.

    All values are seconds (float). The caller supplies the elapsed time
    between samples and the current local date (YYYY-MM-DD); day rollover
    resets the per-day counters before the sample is credited.
    """

    def __init__(self) -> None:
        self.totals: dict[str, float] = {c: 0.0 for c in RUNTIME_CHANNELS}
        self.today: dict[str, float] = {c: 0.0 for c in RUNTIME_CHANNELS}
        self.today_date: str | None = None

    def add_sample(self, main: dict[str, Any], dt: float, today: str) -> bool:
        """Credit dt seconds to the channels active in main. True if changed."""
        if dt <= 0:
            return False
        if self.today_date != today:
            self.today = {c: 0.0 for c in RUNTIME_CHANNELS}
            self.today_date = today
        channels = active_channels(main)
        for channel in channels:
            self.totals[channel] += dt
            self.today[channel] += dt
        return bool(channels)

    def to_dict(self) -> dict[str, Any]:
        return {
            "totals": dict(self.totals),
            "today": dict(self.today),
            "today_date": self.today_date,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "RuntimeCounters":
        counters = cls()
        if not isinstance(data, dict):
            return counters
        for target_name in ("totals", "today"):
            saved = data.get(target_name)
            if isinstance(saved, dict):
                target = getattr(counters, target_name)
                for channel in RUNTIME_CHANNELS:
                    value = saved.get(channel)
                    if isinstance(value, (int, float)) and value >= 0:
                        target[channel] = float(value)
        if isinstance(data.get("today_date"), str):
            counters.today_date = data["today_date"]
        return counters
