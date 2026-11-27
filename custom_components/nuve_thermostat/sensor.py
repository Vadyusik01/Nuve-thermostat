from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .api import NuveApi
from .runtime import async_get_runtime
from .runtime_stats import ACTIVITY_OPTIONS, RuntimeCounters, current_activity
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
            NuveDiagnosticSensor(coordinator, sn, key, name, unit, device_info)
            for key, name, unit in (
                ("current_temp", "Current temperature", "°C"),
                ("current_humidity", "Current humidity", "%"),
                ("co2", "CO₂ status", None),
                ("wifi_name", "Wi-Fi name", None),
                ("wifi_strength", "Wi-Fi strength", "%"),
                ("mode_alias", "Mode alias", None),
                ("client_id", "Client ID", None),
                ("fan", "Fan mode code", None),
                ("current_fan_status", "Fan status", None),
                ("current_heating_stage", "Heating stage", None),
                ("current_cooling_stage", "Cooling stage", None),
                ("current_aux_stage", "Auxiliary heating stage", None),
                ("system_type", "System type", None),
                ("current_timezone", "Thermostat timezone", None),
                ("firmware_version", "Firmware version", None),
                ("alert_count", "Active alerts", None),
            )
        ]
    )

    # Built-in runtime accounting + "what is the equipment doing" sensor.
    tracker = NuveRuntimeTracker(hass, entry, coordinator)
    await tracker.async_load()
    await tracker.async_update()  # baseline timestamp, credits nothing

    @callback
    def _handle_coordinator_update() -> None:
        hass.async_create_task(tracker.async_update())

    entry.async_on_unload(coordinator.async_add_listener(_handle_coordinator_update))

    new_entities: list[SensorEntity] = [NuveActivitySensor(coordinator, sn, device_info)]
    for channel, label, icon in (
        ("heating", "Heating", "mdi:fire"),
        ("cooling", "Cooling", "mdi:snowflake"),
        ("aux", "Auxiliary heating", "mdi:radiator"),
        ("fan", "Fan circulation", "mdi:fan"),
    ):
        for period in ("total", "today"):
            new_entities.append(
                NuveRuntimeSensor(
                    coordinator, tracker, sn, channel, label, period, icon, device_info
                )
            )
    async_add_entities(new_entities)
    _LOGGER.info("Nuve diagnostic sensors added for %s", sn)


class NuveDiagnosticSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, sn: str, key: str, name: str, unit: str | None, device_info) -> None:
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f"nuve_{sn}_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_info = device_info

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        main = data.get("main", {})
        static = data.get("static", {})
        if self.key == "alert_count":
            alerts = data.get("alerts", {})
            if isinstance(alerts, dict):
                alerts = alerts.get("data", alerts.get("result", []))
            return len(alerts) if isinstance(alerts, list) else 0
        if self.key == "firmware_version":
            return static.get("firmware_version") or main.get("firmware_version")
        if self.key == "wifi_name":
            system = main.get("system", {})
            if isinstance(system, dict) and system.get("wifiName") is not None:
                return system.get("wifiName")
            return main.get("wifi_name")
        if self.key == "wifi_strength":
            system = main.get("system", {})
            value = system.get("wifiStrength") if isinstance(system, dict) else None
            if value is None:
                value = main.get("wifi_strength")
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                return None
        return main.get(self.key)


# Poll is 30 s; never credit more than this for one interval, so a stalled
# coordinator or an HA restart gap cannot inflate the counters.
_MAX_CREDIT_SECONDS = 180.0
_SAVE_EVERY_SECONDS = 300.0


class NuveRuntimeTracker:
    """Feeds status-coordinator samples into RuntimeCounters and persists
    them in a Store (survives restarts, like the backlight palette)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
        self._store: Store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.runtime")
        self._coordinator = coordinator
        self.counters = RuntimeCounters()
        self._last_ts: float | None = None
        self._last_save: float = 0.0

    async def async_load(self) -> None:
        try:
            saved = await self._store.async_load()
        except Exception:
            saved = None
        self.counters = RuntimeCounters.from_dict(saved)

    def _save_data(self) -> dict[str, Any]:
        return self.counters.to_dict()

    async def async_update(self) -> None:
        now = time.monotonic()
        if self._last_ts is None:
            self._last_ts = now
            return
        dt = min(now - self._last_ts, _MAX_CREDIT_SECONDS)
        self._last_ts = now
        data = self._coordinator.data or {}
        main = data.get("main", {}) if isinstance(data, dict) else {}
        if not isinstance(main, dict) or not main:
            return
        today = dt_util.now().date().isoformat()
        if not self.counters.add_sample(main, dt, today):
            return
        if time.time() - self._last_save >= _SAVE_EVERY_SECONDS:
            self._last_save = time.time()
            await self._store.async_save(self._save_data())
        else:
            self._store.async_delay_save(self._save_data, 60)


_ACTIVITY_ICONS = {
    "heating": "mdi:fire",
    "cooling": "mdi:snowflake",
    "aux_heat": "mdi:radiator",
    "fan": "mdi:fan",
    "idle": "mdi:power-sleep",
    "off": "mdi:power",
}


class NuveActivitySensor(CoordinatorEntity, SensorEntity):
    """What the equipment is doing right now (not the selected mode)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ACTIVITY_OPTIONS
    _attr_translation_key = "current_activity"
    _attr_icon = "mdi:power-sleep"

    def __init__(self, coordinator, sn: str, device_info) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"nuve_{sn}_current_activity"
        self._attr_device_info = device_info

    @property
    def _main(self) -> dict:
        data = self.coordinator.data or {}
        main = data.get("main", {}) if isinstance(data, dict) else {}
        return main if isinstance(main, dict) else {}

    @property
    def native_value(self):
        return current_activity(self._main)

    @property
    def icon(self):
        return _ACTIVITY_ICONS.get(self.native_value, "mdi:power-sleep")

    @property
    def extra_state_attributes(self):
        main = self._main
        return {
            key: main[key]
            for key in (
                "current_heating_stage",
                "current_cooling_stage",
                "current_aux_stage",
                "current_fan_status",
            )
            if key in main
        }


class NuveRuntimeSensor(CoordinatorEntity, SensorEntity):
    """Accumulated equipment runtime in hours (total or today)."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "h"
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator,
        tracker: NuveRuntimeTracker,
        sn: str,
        channel: str,
        label: str,
        period: str,
        icon: str,
        device_info,
    ) -> None:
        super().__init__(coordinator)
        self.tracker = tracker
        self.channel = channel
        self.period = period
        self._attr_name = f"{label} runtime {period}"
        self._attr_unique_id = f"nuve_{sn}_runtime_{channel}_{period}"
        self._attr_icon = icon
        self._attr_device_info = device_info

    @property
    def native_value(self) -> float:
        counters = self.tracker.counters
        seconds = (
            counters.totals[self.channel]
            if self.period == "total"
            else counters.today[self.channel]
        )
        return round(seconds / 3600, 2)
