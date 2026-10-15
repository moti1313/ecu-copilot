"""Thin HTTP client for the twin. The agent's tools call this; nothing else talks to the twin."""

from __future__ import annotations

import httpx

from .. import config


class TwinClient:
    def __init__(self, base_url: str | None = None, timeout: float = 5.0) -> None:
        self._client = httpx.Client(base_url=base_url or config.TWIN_URL, timeout=timeout)

    def health(self) -> dict:
        return self._client.get("/health").raise_for_status().json()

    def stats(self, minutes: int = 10) -> dict:
        return self._client.get("/stats", params={"minutes": minutes}).raise_for_status().json()

    def results(
        self,
        *,
        station: int | None = None,
        variant: str | None = None,
        minutes: int | None = None,
        only_failed: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        params: dict = {"only_failed": only_failed, "limit": limit}
        if station is not None:
            params["station"] = station
        if variant is not None:
            params["variant"] = variant
        if minutes is not None:
            params["minutes"] = minutes
        return self._client.get("/results", params=params).raise_for_status().json()

    def add_fault(self, fault: dict) -> dict:
        return self._client.post("/faults", json=fault).raise_for_status().json()

    def clear_faults(self) -> dict:
        return self._client.delete("/faults").raise_for_status().json()
