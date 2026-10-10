from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .api import NuveApi
from .mode_backlight import mode_key, mode_settings
from .runtime import async_get_runtime
from .const import (
    DOMAIN,
    CONF_DEVICE_SN,
    CONF_CONTRACTOR_NAME,
    CONF_CONTRACTOR_BRAND,
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

PRESET_VACATION = "vacation"
PRESET_AUX_HEAT = "aux_heat"

# id режима -> preset. Гипотеза из разбора APK (SystemMode.Value:
# Cooling, Heating, Auto, Vacation, Off, EmergencyHeat), требует
# MITM-подтверждения. До подтверждения режимы 4/6 обрабатываются
# осторожно: HVACMode либо сохраняется, либо HEAT.
MODE_ID_TO_PRESET = {
    4: PRESET_VACATION,
    6: PRESET_AUX_HEAT,
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
        runtime = await async_get_runtime(hass, entry)
        api = runtime.api
        coordinator = runtime.status_coordinator
        sn = runtime.sn
        climate = NuveClimate(
            coordinator,
            api,
            sn,
            entry.data.get(CONF_CONTRACTOR_NAME, ""),
            entry.data.get(CONF_CONTRACTOR_BRAND, ""),
        )
        settings = mode_settings(hass, DOMAIN, entry.entry_id)

        async def apply_mode_backlight() -> None:
            if not settings.get("enabled"):
                return
            climate_data = climate._d
            selected_mode = mode_key(climate_data, climate.hvac_mode, climate.preset_mode)
            # Диагностика 0.9.3: видно, по каким значениям стадий выбран режим.
            # Включить в configuration.yaml:
            #   logger:
            #     logs:
            #       custom_components.nuve_thermostat: debug
            _LOGGER.debug(
                "mode_key for %s: aux_stage=%s cool_stage=%s heat_stage=%s "
                "fan_status=%s hvac=%s preset=%s -> %s",
                sn,
                climate_data.get("current_aux_stage"),
                climate_data.get("current_cooling_stage"),
                climate_data.get("current_heating_stage"),
                climate_data.get("current_fan_status"),
                climate.hvac_mode,
                climate.preset_mode,
                selected_mode,
            )
            mode_values = settings["modes"][selected_mode]
            applied = settings.get("last_applied")
            signature = (
                selected_mode,
                mode_values["hue"],
                mode_values["saturation"],
                mode_values["value"],
                mode_values["shadeIndex"],
            )
            if applied == signature:
                return
            try:
                current_backlight = runtime.backlight_coordinator.data or {
                    "value_scale": 1.0
                }
                await api.set_backlight(
                    sn,
                    on=True,
                    hue=mode_values["hue"],
                    saturation=mode_values["saturation"],
                    value=mode_values["value"],
                    shade_index=mode_values["shadeIndex"],
                    value_scale=current_backlight["value_scale"],
                )
            except Exception:
                _LOGGER.exception("Unable to apply automatic backlight for %s", sn)
                return
            settings["last_applied"] = signature
            await runtime.backlight_coordinator.async_request_refresh()
            _LOGGER.debug("Applied %s backlight slider values %s for %s", selected_mode, mode_values, sn)

        settings["apply"] = apply_mode_backlight
        coordinator.async_add_listener(
            lambda: hass.async_create_task(apply_mode_backlight())
        )
        _LOGGER.debug(
            "Nuve coordinator data keys: %s",
            list((coordinator.data or {}).keys())
            if isinstance(coordinator.data, dict)
            else type(coordinator.data),
        )
        async_add_entities(
            [
                climate
            ]
        )
        await apply_mode_backlight()
        _LOGGER.debug("Nuve climate entity added OK")
    except Exception:
        _LOGGER.exception("Nuve climate setup FAILED")
        raise


class NuveClimate(CoordinatorEntity, ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
    )
    _attr_hvac_modes = [
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.AUTO,
    ]
    _attr_preset_modes = [PRESET_VACATION, PRESET_AUX_HEAT]

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
        self._last_hvac_mode = HVACMode.AUTO

    @property
    def _d(self) -> dict[str, Any]:
        d = self.coordinator.data
        if not isinstance(d, dict):
            return {}
        main = d.get("main")
        return main if isinstance(main, dict) else d

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
            mode_int = int(mode)
        except (TypeError, ValueError):
            return HVACMode.OFF
        if mode_int == 4:
            # Vacation: HVACMode не меняем, показываем последний известный
            return self._last_hvac_mode
        if mode_int == 6:
            # EmergencyHeat: по конвенциям HA это HEAT
            self._last_hvac_mode = HVACMode.HEAT
            return HVACMode.HEAT
        mapped = MODE_MAP.get(mode_int, HVACMode.OFF)
        self._last_hvac_mode = mapped
        return mapped

    @property
    def preset_mode(self):
        mode = self._get("mode", default=0)
        try:
            preset = MODE_ID_TO_PRESET.get(int(mode))
        except (TypeError, ValueError):
            preset = None
        if preset is None:
            # Запасной вариант: у устройства есть отдельный флаг vacation
            vac = self._get("is_vacation", "vacation")
            if isinstance(vac, bool) and vac:
                return PRESET_VACATION
            if str(vac).lower() in ("true", "1", "on", "yes"):
                return PRESET_VACATION
        return preset

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

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode == PRESET_VACATION:
            api_mode = 4
        elif preset_mode == PRESET_AUX_HEAT:
            api_mode = 6
        else:
            return
        await self.api.set_mode(self.sn, api_mode)
        await self.coordinator.async_request_refresh()
