from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
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
    SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    api = NuveApi(entry.data[CONF_API_URL], async_get_clientsession(hass))
    await api.login(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    sn = entry.data[CONF_DEVICE_SN]

    try:
        static_info = await api.get_static_info(sn)
        if isinstance(static_info, dict) and isinstance(static_info.get("data"), dict):
            static_info = static_info["data"]
        if not isinstance(static_info, dict):
            static_info = {}
    except Exception as exc:
        _LOGGER.debug("Nuve static info unavailable: %s", exc)
        static_info = {}

    async def update() -> dict[str, Any]:
        main = await api.main_data(sn)
        if isinstance(main, dict) and isinstance(main.get("data"), dict):
            main = main["data"]
        if not isinstance(main, dict):
            main = {}
        try:
            alerts = await api.get_alerts(sn)
        except Exception as exc:
            _LOGGER.debug("Nuve alerts unavailable: %s", exc)
            alerts = {}
        return {"main": main, "static": static_info, "alerts": alerts}

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"Nuve diagnostics {sn}",
        update_method=update,
        update_interval=timedelta(seconds=SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()
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
