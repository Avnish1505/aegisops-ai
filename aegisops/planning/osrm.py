"""Road travel times from an OSRM server's table service.

One ``/table/v1/{profile}`` request per scenario gives durations from every resource to every
incident. Matrices are cached by a hash of the request (server, profile, IDs and coordinates), so
replanning the same situation never re-queries OSRM.

If OSRM cannot be reached or answers with an error, the provider falls back to straight-line
estimates and marks the matrix ``degraded`` with a reason; the verifier and the console both
surface that flag. Pairs OSRM cannot route (``null`` durations) also fall back, per pair, and
mark the matrix degraded. Degraded matrices are not cached, so the next plan retries OSRM.

Durations are OSRM's car-profile free-flow estimates: no live traffic, closures or flooding.
"""

from __future__ import annotations

from collections import OrderedDict

import httpx

from aegisops.domain.canonical import canonical_json, sha256_hex
from aegisops.domain.models import Scenario
from aegisops.planning.travel import StraightLineProvider, TravelTimeMatrix, TravelTimeProvider


class OSRMProvider:
    def __init__(
        self,
        base_url: str,
        *,
        profile: str = "driving",
        client: httpx.Client | None = None,
        timeout_s: float = 5.0,
        cache_size: int = 256,
        fallback: TravelTimeProvider | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._profile = profile
        self._client = client or httpx.Client(timeout=timeout_s)
        self._cache: OrderedDict[str, TravelTimeMatrix] = OrderedDict()
        self._cache_size = cache_size
        self._fallback = fallback or StraightLineProvider()
        self.name = f"osrm-{profile}"

    def cache_key(self, scenario: Scenario) -> str:
        return sha256_hex(
            canonical_json(
                {
                    "server": self._base_url,
                    "profile": self._profile,
                    "resources": [
                        [r.id, r.location.lat, r.location.lon] for r in scenario.resources
                    ],
                    "incidents": [
                        [i.id, i.location.lat, i.location.lon] for i in scenario.incidents
                    ],
                }
            )
        )

    def matrix(self, scenario: Scenario) -> TravelTimeMatrix:
        key = self.cache_key(scenario)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        try:
            matrix = self._fetch(scenario)
        except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError) as error:
            return self._fallback.matrix(scenario).model_copy(
                update={
                    "degraded": True,
                    "degraded_reason": (
                        f"OSRM unavailable ({type(error).__name__}); "
                        f"straight-line estimates from {self._fallback.name}"
                    ),
                }
            )
        if not matrix.degraded:
            self._cache[key] = matrix
            if len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return matrix

    def _fetch(self, scenario: Scenario) -> TravelTimeMatrix:
        resources, incidents = scenario.resources, scenario.incidents
        if not resources:
            return TravelTimeMatrix(provider=self.name, minutes={})
        locations = [r.location for r in resources] + [i.location for i in incidents]
        # OSRM wants lon,lat (GeoJSON order), not lat,lon.
        coordinates = ";".join(f"{loc.lon:.6f},{loc.lat:.6f}" for loc in locations)
        response = self._client.get(
            f"{self._base_url}/table/v1/{self._profile}/{coordinates}",
            params={
                "sources": ";".join(str(i) for i in range(len(resources))),
                "destinations": ";".join(
                    str(len(resources) + i) for i in range(len(incidents))
                ),
                "annotations": "duration",
            },
        )
        response.raise_for_status()
        body = response.json()
        if body.get("code") != "Ok":
            raise ValueError(f"OSRM answered {body.get('code')}: {body.get('message')}")
        durations = body["durations"]
        fallback: TravelTimeMatrix | None = None
        unroutable = 0
        minutes: dict[str, dict[str, float]] = {}
        for row, resource in enumerate(resources):
            minutes[resource.id] = {}
            for column, incident in enumerate(incidents):
                seconds = durations[row][column]
                if seconds is None:
                    unroutable += 1
                    fallback = fallback or self._fallback.matrix(scenario)
                    estimate = fallback.get(resource.id, incident.id)
                    if estimate is None:
                        raise ValueError(f"no fallback estimate for {resource.id}->{incident.id}")
                    minutes[resource.id][incident.id] = estimate
                else:
                    minutes[resource.id][incident.id] = float(seconds) / 60
        if unroutable:
            return TravelTimeMatrix(
                provider=self.name,
                minutes=minutes,
                degraded=True,
                degraded_reason=(
                    f"OSRM could not route {unroutable} of {len(resources) * len(incidents)} "
                    f"pairs; straight-line estimates from {self._fallback.name} used for them"
                ),
            )
        return TravelTimeMatrix(provider=self.name, minutes=minutes)
