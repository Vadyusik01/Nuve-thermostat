from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class NuveApi:
    def __init__(self, api_url: str, session: aiohttp.ClientSession):
        self.api_url = api_url.rstrip("/")
        self.session = session
        self.token: str | None = None

    def _headers(self) -> dict[str, str]:
        h = {
            "Accept": "application/json",
            "Content-Type": "application/json; charset=UTF-8",
        }
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    async def request(self, method: str, path: str, **kwargs) -> Any:
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

            if r.status >= 400:
                raise RuntimeError(f"Nuve API {r.status}: {data}")
            return data

    async def login(self, email: str, password: str) -> Any:
        data = await self.request(
            "POST",
            "/login",
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
        # id = код режима (1..6), устройство = sn
        try:
            mode_num = int(mode)
        except (TypeError, ValueError):
            mode_num = mode

        payloads = [
            {"sn": sn, "id": mode_num},
            {"sn": sn, "id": mode_num, "mode": mode_num},
            {"sn": sn, "mode": mode_num, "id": mode_num},
            {"id": mode_num, "sn": sn},
        ]
        last_error = None
        for payload in payloads:
            try:
                _LOGGER.debug("set_mode attempt for device %s", sn)
                result = await self.request("POST", "/device/mode", json=payload)
                _LOGGER.debug("set_mode accepted for device %s", sn)
                return result
            except Exception as exc:
                last_error = exc
                _LOGGER.debug("set_mode attempt failed for device %s: %s", sn, exc)

        raise RuntimeError(f"No working set_mode payload: {last_error}")

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