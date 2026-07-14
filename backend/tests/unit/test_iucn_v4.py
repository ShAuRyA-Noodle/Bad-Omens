"""Unit test for the IUCN Red List API v4 parsing (worker.pipeline.conservation).

Mocks the two v4 calls (taxa lookup + assessment detail) so the parsing of
category / year / population trend is pinned without hitting the network.
"""
from __future__ import annotations

from typing import Any

from worker.pipeline import conservation as cons


class _FakeResp:
    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status_code = status
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise AssertionError(f"HTTP {self.status_code}")


class _FakeClient:
    """Stands in for httpx.Client; routes by URL to canned v4 responses."""

    def __init__(self, *_: Any, **__: Any) -> None:
        pass

    def __enter__(self) -> _FakeClient:
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeResp:
        if "taxa/scientific_name" in url:
            return _FakeResp(200, {
                "assessments": [
                    {"latest": False, "red_list_category_code": "VU", "year_published": "2008",
                     "assessment_id": 111, "scopes": [{"description": {"en": "Global"}}]},
                    {"latest": True, "red_list_category_code": "EN", "year_published": "2018",
                     "assessment_id": 222, "scopes": [{"description": {"en": "Global"}}]},
                ]
            })
        if "assessment/222" in url:
            return _FakeResp(200, {"population_trend": {"description": {"en": "Decreasing"}, "code": "1"}})
        return _FakeResp(404, {})


def test_iucn_v4_populates_category_year_and_trend(monkeypatch) -> None:
    monkeypatch.setattr(cons.httpx, "Client", _FakeClient)
    record = cons.ConservationRecord(species="Tor putitora")
    cons._iucn_lookup(record, "Tor putitora", token="fake-token")

    # latest global assessment wins (EN/2018), not the older VU/2008
    assert record.iucn_category == "EN"
    assert record.iucn_category_full == "Endangered"
    assert record.iucn_assessment_year == 2018
    assert record.iucn_population_trend == "Decreasing"


def test_iucn_v4_skips_genus_only_names(monkeypatch) -> None:
    called = False

    class _Boom(_FakeClient):
        def get(self, url: str, params: dict[str, Any] | None = None) -> _FakeResp:
            nonlocal called
            called = True
            return super().get(url, params)

    monkeypatch.setattr(cons.httpx, "Client", _Boom)
    record = cons.ConservationRecord(species="Tor")  # genus only
    cons._iucn_lookup(record, "Tor", token="fake-token")
    assert record.iucn_category is None
    assert called is False  # never even calls the API without a binomial
