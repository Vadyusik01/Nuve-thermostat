from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .api import NuveApi
from .const import (
    DOMAIN,
    CONF_API_URL,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_DEVICE_SN,
    CONF_CONTRACTOR_NAME,
    CONF_CONTRACTOR_BRAND,
    SCAN_INTERVAL as POLL_SECONDS,
    INTEGRATION_VERSION,
)

_LOGGER = logging.getLogger(__name__)

try:
    from homeassistant.components.climate import HVACMode, HVACAction, ClimateEntityFeature
except ImportError:
    from homeassistant.components.climate.const import (  # type: ignore
        HVACMode,
        HVACAction,
        ClimateEntityFeature,
    )

# Числовой mode из API / поле id при записи (1..6)
MODE_MAP = {
    0: HVACMode.OFF,
    1: HVACMode.COOL,
    2: HVACMode.HEAT,
    3: HVACMode.AUTO,
    5: HVACMode.OFF,   # запасной вариант для Off
    6: HVACMode.OFF,
}

MODE_ALIAS_MAP = {
    "off": HVACMode.OFF,
    "cooling": HVACMode.COOL,
    "cool": HVACMode.COOL,
    "heating": HVACMode.HEAT,
    "heat": HVACMode.HEAT,
    "auto": HVACMode.AUTO,
}

# Что отправляем в API как id (режим). Off пробуем 5, если 0 не примет сервер
HVAC_TO_API = {
    HVACMode.OFF: 5,
    HVACMode.COOL: 1,
    HVACMode.HEAT: 2,
    HVACMode.AUTO: 3,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities,
) -> None:
    try:
        _LOGGER.info(
            "Nuve Thermostat integration %s starting for %s",
            INTEGRATION_VERSION,
            entry.data.get(CONF_DEVICE_SN),
        )
        api = NuveApi(entry.data[CONF_API_URL], async_get_clientsession(hass))
        await api.login(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
        sn = entry.data[CONF_DEVICE_SN]

        async def update():
            data = await api.main_data(sn)
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                return data["data"]
            return data

        coordinator = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=f"Nuve {sn}",
            update_method=update,
            update_interval=timedelta(seconds=POLL_SECONDS),
        )
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.warning(
            "Nuve coordinator data keys: %s",
            list((coordinator.data or {}).keys())
            if isinstance(coordinator.data, dict)
            else type(coordinator.data),
        )
        async_add_entities(
            [
                NuveClimate(
                    coordinator,
                    api,
                    sn,
                    entry.data.get(CONF_CONTRACTOR_NAME, ""),
                    entry.data.get(CONF_CONTRACTOR_BRAND, ""),
                )
            ]
        )
        _LOGGER.warning("Nuve climate entity added OK")
    except Exception:
        _LOGGER.exception("Nuve climate setup FAILED")
        raise


class NuveClimate(CoordinatorEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.AUTO,
    ]

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
        self.contractor_name = contractor_name
        self.contractor_brand = contractor_brand
        self._attr_name = f"Nuve {sn}"
        self._attr_unique_id = f"nuve_{sn}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, sn)},
            name=f"Nuve Thermostat {sn}",
            manufacturer=contractor_name or "Nuve Controls LLC",
            model=contractor_brand or "Nuve HVAC thermostat",
            sw_version=INTEGRATION_VERSION,
        )

    @property
    def _d(self) -> dict[str, Any]:
        d = self.coordinator.data
        return d if isinstance(d, dict) else {}

    def _get(self, *keys, default=None):
        for k in keys:
            if k in self._d and self._d[k] is not None:
                return self._d[k]
        return default

    @property
    def available(self) -> bool:
        online = self._get("is_device_online")
        if online is not None:
            return str(online).lower() in ("online", "true", "1")
        return True

    @property
    def current_temperature(self):
        v = self._get("current_temp", "temp")
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def target_temperature(self):
        v = self._get("temp", "requestedTemp", "target_temp")
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def current_humidity(self):
        v = self._get("current_humidity", "humidity")
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    @property
    def hvac_mode(self):
        alias = self._get("mode_alias")
        if alias is not None:
            mapped = MODE_ALIAS_MAP.get(str(alias).lower().strip())
            if mapped is not None:
                return mapped
        mode = self._get("mode", default=0)
        try:
            return MODE_MAP.get(int(mode), HVACMode.OFF)
        except (TypeError, ValueError):
            return HVACMode.OFF

    @property
    def hvac_action(self):
        try:
            cooling = self._get("current_cooling_stage")
            heating = self._get("current_heating_stage")
            if cooling is not None and int(cooling) > 0:
                return HVACAction.COOLING
            if heating is not None and int(heating) > 0:
                return HVACAction.HEATING
        except (TypeError, ValueError):
            pass
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self):
        attrs = {"nuve_serial_number": self.sn}
        for k in (
            "co2",
            "fan",
            "locked",
            "is_vacation",
            "hold_status",
            "system_type",
            "is_device_online",
            "mode",
            "mode_alias",
            "current_fan_status",
            "client_id",
        ):
            if k in self._d:
                attrs[k] = self._d[k]
        system = self._d.get("system")
        if isinstance(system, dict):
            if "wifiName" in system:
                attrs["wifi_name"] = system["wifiName"]
            if "wifiStrength" in system:
                attrs["wifi_strength"] = system["wifiStrength"]
        if self.current_humidity is not None:
            attrs["humidity"] = self.current_humidity
        return attrs

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        await self.api.set_temperature(self.sn, float(temp))
        await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode):
        api_mode = HVAC_TO_API.get(hvac_mode, 1)
        await self.api.set_mode(self.sn, api_mode)
        await self.coordinator.async_request_refresh()
