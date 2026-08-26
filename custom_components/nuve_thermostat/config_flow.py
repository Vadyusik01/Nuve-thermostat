from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NuveApi
from .const import (
    CONF_API_URL,
    CONF_CONTRACTOR_BRAND,
    CONF_CONTRACTOR_NAME,
    CONF_DEVICE_SN,
    CONF_EMAIL,
    CONF_PASSWORD,
    DEFAULT_API,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class NuveFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    def __init__(self) -> None:
        self._api: NuveApi | None = None
        self._email = ""
        self._password = ""
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            self._email = user_input[CONF_EMAIL].strip()
            self._password = user_input[CONF_PASSWORD]
            self._api = NuveApi(DEFAULT_API, async_get_clientsession(self.hass))
            try:
                await self._api.login(self._email, self._password)
                self._devices = self._normalise_devices(await self._api.get_devices())
                if not self._devices:
                    errors["base"] = "no_devices"
                elif len(self._devices) == 1:
                    return await self._create_device_entry(self._devices[0])
                else:
                    return await self.async_step_select_device()
            except Exception as exc:
                _LOGGER.exception("Nuve automatic device discovery failed: %s", exc)
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_select_device(self, user_input=None):
        if user_input:
            selected_sn = user_input[CONF_DEVICE_SN]
            device = next(
                (item for item in self._devices if item[CONF_DEVICE_SN] == selected_sn),
                None,
            )
            if device is not None:
                return await self._create_device_entry(device)

        options = {
            item[CONF_DEVICE_SN]: self._device_label(item) for item in self._devices
        }
        schema = vol.Schema({vol.Required(CONF_DEVICE_SN): vol.In(options)})
        return self.async_show_form(step_id="select_device", data_schema=schema)

    async def _create_device_entry(self, device: dict[str, Any]):
        sn = device[CONF_DEVICE_SN]
        await self.async_set_unique_id(f"device_{sn}")
        self._abort_if_unique_id_configured()

        contractor_name = ""
        contractor_brand = ""
        if self._api is not None:
            contractor = await self._api.get_contractor(sn)
            if isinstance(contractor, dict):
                contractor = contractor.get("data", contractor)
            if isinstance(contractor, dict):
                contractor_name = str(contractor.get("name") or "")
                contractor_brand = str(contractor.get("brand") or "")

        title = str(device.get("device_name") or contractor_name or f"Nuve {sn}")
        return self.async_create_entry(
            title=title,
            data={
                CONF_API_URL: DEFAULT_API,
                CONF_EMAIL: self._email,
                CONF_PASSWORD: self._password,
                CONF_DEVICE_SN: sn,
                CONF_CONTRACTOR_NAME: contractor_name,
                CONF_CONTRACTOR_BRAND: contractor_brand,
            },
        )

    @staticmethod
    def _normalise_devices(response: Any) -> list[dict[str, Any]]:
        if isinstance(response, dict):
            response = response.get("data", response.get("result", []))
        if not isinstance(response, list):
            return []

        devices = []
        for raw in response:
            if not isinstance(raw, dict):
                continue
            sn = raw.get("serial_number") or raw.get("sn") or raw.get("deviceSN")
            if sn:
                devices.append(
                    {
                        CONF_DEVICE_SN: str(sn),
                        "device_name": raw.get("device_name") or raw.get("name"),
                        "location": raw.get("location"),
                    }
                )
        return devices

    @staticmethod
    def _device_label(device: dict[str, Any]) -> str:
        sn = device[CONF_DEVICE_SN]
        name = device.get("device_name") or device.get("location")
        return f"{name} ({sn})" if name else sn
