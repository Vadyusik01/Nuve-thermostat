from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class NuveApi:
    def __init__(self, api_url: str, session: aiohttp.ClientSession):
        self.api_url = api_url.rstrip("/")
        self.session = session
        self.token: str | None = None
        self._email: str | None = None
        self._password: str | None = None
        self._reauth_lock = asyncio.Lock()

    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def request(
        self,
        method: str,
        path: str,
        *,
        _retry: bool = True,
        **kwargs,
    ) -> Any:
        url = f"{self.api_url}{path}"
        _LOGGER.debug("Nuve API %s %s", method, url)
        async with self.session.request(
            method,
            url,
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=20),
            **kwargs,
        ) as r:
            text = await r.text()
            try:
                data = await r.json(content_type=None) if text else {}
            except Exception:
                data = {"_raw": text}

            if r.status == 401 and _retry and path != "/login":
                if self._email and self._password:
                    _LOGGER.warning("Nuve API 401 on %s, re-login and retry", path)
                    async with self._reauth_lock:
                        await self.login(self._email, self._password)
                    return await self.request(method, path, _retry=False, **kwargs)
                raise RuntimeError(f"Nuve API 401: {data}")

            if r.status >= 400:
                raise RuntimeError(f"Nuve API {r.status}: {data}")
            return data

    async def login(self, email: str, password: str) -> Any:
        self._email = email
        self._password = password
        data = await self.request(
            "POST",
            "/login",
            _retry=False,
            json={"mail": email, "password": password},
        )
        _LOGGER.debug(
            "Login response keys: %s",
            list(data.keys()) if isinstance(data, dict) else type(data),
        )

        token = None
        if isinstance(data, dict):
            for key in ("token", "accessToken", "access_token"):
                if isinstance(data.get(key), str) and data[key]:
                    token = data[key]
                    break
            if not token:
                for wrapper in ("data", "result", "user", "payload"):
                    obj = data.get(wrapper)
                    if isinstance(obj, dict):
                        for key in ("token", "accessToken", "access_token"):
                            if isinstance(obj.get(key), str) and obj[key]:
                                token = obj[key]
                                break
                    if token:
                        break

        if not token:
            raise RuntimeError(f"Login OK but no token found. Response: {data}")
        self.token = token
        _LOGGER.info("Nuve login OK, token length=%s", len(token))
        return data

    async def get_devices(self) -> Any:
        """Return devices visible to the authenticated user."""
        return await self.request(
            "GET",
            "/getSn",
            params={"only_own_devices": "false"},
        )

    async def get_contractor(self, sn: str) -> Any:
        """Return contractor/brand metadata for a device."""
        return await self.request("GET", f"/getContractor/{sn}")

    async def get_alerts(self, sn: str) -> Any:
        """Return alerts for a device."""
        return await self.request("GET", "/device/alerts", params={"sn": sn})

    async def get_static_info(self, sn: str) -> Any:
        """Return static device information."""
        return await self.request("GET", "/device/static-info", params={"sn": sn})

    async def main_data(self, sn: str) -> Any:
        return await self.request("GET", "/device/main-data", params={"sn": sn})

    async def set_temperature(self, sn: str, temp_c: float) -> Any:
        return await self.request(
            "POST",
            "/device/temperature",
            json={"sn": sn, "temp": temp_c},
        )

    async def set_mode(
        self,
        sn: str,
        mode: Any,
        client_id: int | str | None = None,
    ) -> Any:
        """Set HVAC mode. API expects id in 1..6 and device serial as sn."""
        try:
            mode_num = int(mode)
        except (TypeError, ValueError):
            mode_num = mode
        payload = {"sn": sn, "id": mode_num}
        _LOGGER.debug("set_mode %s", payload)
        return await self.request("POST", "/device/mode", json=payload)

    async def get_fan(self, sn: str) -> Any:
        return await self.request("GET", "/device/fan", params={"sn": sn})

    async def set_fan(self, sn: str, mode: int, working_per_hour: int) -> Any:
        return await self.request(
            "POST",
            "/device/fan",
            json={
                "sn": sn,
                "mode": mode,
                "workingPerHour": working_per_hour,
            },
        )

    async def get_backlight(self, sn: str) -> Any:
        """Return the device backlight HSV settings."""
        return await self.request(
            "GET",
            "/device/backlight/hsv",
            params={"sn": sn},
        )

    async def set_backlight(
        self,
        sn: str,
        *,
        on: bool,
        hue: float,
        saturation: float = 100.0,
        value: float,
        shade_index: float,
        value_scale: float = 1.0,
    ) -> Any:
        """Set backlight HSV settings using the mobile app's field names.

        Home Assistant entities expose saturation/value as percentages. The
        mobile API uses fractional HSV components, so they are converted to
        0..1 here. ``value_scale`` is retained for compatibility with devices
        whose GET response uses the older 0..100 representation.
        """
        api_value = value / 100.0 if value_scale == 1.0 else value
        # HA UI: hue degrees 0..360. Nuve API: fractional hue 0..1 (confirmed).
        api_hue = (float(hue) / 360.0) if float(hue) > 1.0 else float(hue)
        # Keep saturation usable: if HA has 0 (white), colour changes look like "nothing".
        sat = float(saturation)
        if sat <= 0:
            sat = 100.0
        api_sat = sat / 100.0 if sat > 1.0 else sat
        # shadeIndex: leave as provided (0.9.6 /100 made some devices stick on white)
        # sn in query + body
        return await self.request(
            "POST",
            "/device/backlight/hsv",
            params={"sn": sn},
            json={
                "sn": sn,
                "on": on,
                "isOn": on,
                "hue": api_hue,
                "saturation": api_sat,
                "value": api_value,
                "shadeIndex": float(shade_index),
            },
        )

    async def get_backlight_rgb(self, sn: str) -> Any:
        """Return legacy RGB/backlight state when supported by the device."""
        return await self.request(
            "GET",
            "/device/backlight",
            params={"sn": sn},
        )

    async def set_backlight_rgb(
        self,
        sn: str,
        *,
        red: int,
        green: int,
        blue: int,
        state: bool,
        blink_type: int = 0,
    ) -> Any:
        """Set legacy RGB/backlight state when supported by the device."""
        return await self.request(
            "POST",
            "/device/backlight",
            json={
                "sn": sn,
                "r": red,
                "g": green,
                "b": blue,
                "state": state,
                "blink_type": blink_type,
            },
        )
