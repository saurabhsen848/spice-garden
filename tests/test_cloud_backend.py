from datetime import date, timedelta

import pytest
import requests

from agent import config, tools
from mock_api import services


def next_weekday(weekday: int) -> date:
    day = date.today() + timedelta(days=1)
    while day.weekday() != weekday:
        day += timedelta(days=1)
    return day


class FakeResponse:
    ok = True

    @staticmethod
    def json():
        return {"order_id": "ORD1003", "status": "Preparing"}


def test_config_reads_environment_before_streamlit_secret():
    assert config._configured_value(
        "GOOGLE_API_KEY", environ={"GOOGLE_API_KEY": "env-value"},
        secrets={"GOOGLE_API_KEY": "cloud-value"},
    ) == "env-value"


def test_config_reads_streamlit_secret_and_api_url_default():
    assert config._configured_value(
        "GOOGLE_API_KEY", environ={}, secrets={"GOOGLE_API_KEY": "cloud-value"},
    ) == "cloud-value"
    assert config._configured_value("API_BASE_URL", "http://127.0.0.1:8000", environ={}, secrets={}) == \
        "http://127.0.0.1:8000"


def test_config_loads_streamlit_secrets(monkeypatch):
    monkeypatch.setattr(config, "_streamlit_secrets", lambda: {"GOOGLE_API_KEY": "cloud-secret"})
    assert config._configured_value("GOOGLE_API_KEY", environ={}) == "cloud-secret"


def test_missing_gemini_key_error_is_safe(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", None)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY is not configured"):
        config.require_google_api_key()


def test_local_api_mode_is_preferred(monkeypatch):
    monkeypatch.setattr(tools.requests, "request", lambda *args, **kwargs: FakeResponse())
    assert tools._call_api("GET", "/orders/ORD1003")["status"] == "Preparing"


def test_backend_mode_reports_connected(monkeypatch):
    monkeypatch.setattr(tools.requests, "get", lambda *args, **kwargs: FakeResponse())
    assert tools.backend_mode() == "connected"


def test_cloud_mode_looks_up_existing_order_after_api_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("unavailable")

    monkeypatch.setattr(tools.requests, "request", unavailable)
    monkeypatch.setattr(tools.requests, "get", unavailable)
    assert tools._call_api("GET", "/orders/ord1003")["status"] == "Preparing"
    assert tools.backend_mode() == "cloud"


def test_in_process_availability_and_reservation_creation(monkeypatch, tmp_path):
    reservations_path = tmp_path / "reservations.json"
    monkeypatch.setattr(services, "RESERVATIONS_FILE", reservations_path)

    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("unavailable")

    monkeypatch.setattr(tools.requests, "request", unavailable)
    day = next_weekday(2)
    available = tools._call_api(
        "GET", "/reservations/availability",
        params={"date": day.isoformat(), "time": "20:00", "party_size": 2},
    )
    assert available["available"] is True

    created = tools._call_api("POST", "/reservations", json={
        "name": "Test Guest", "phone": "9876543210", "date": day.isoformat(),
        "time": "20:00", "party_size": 2,
    })
    assert created["status"] == "confirmed"
    assert tools._call_api(
        "GET", "/reservations/availability",
        params={"date": day.isoformat(), "time": "20:00", "party_size": 2},
    )["tables_left"] == services.TABLES_PER_SLOT - 1


def test_in_process_uses_weekend_overnight_hours_and_rejects_closed_time(monkeypatch, tmp_path):
    monkeypatch.setattr(services, "RESERVATIONS_FILE", tmp_path / "reservations.json")

    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("unavailable")

    monkeypatch.setattr(tools.requests, "request", unavailable)
    saturday = next_weekday(5)
    sunday = saturday + timedelta(days=1)
    assert isinstance(tools._call_api(
        "GET", "/reservations/availability",
        params={"date": sunday.isoformat(), "time": "01:30", "party_size": 2},
    ), dict)
    closed = tools._call_api(
        "GET", "/reservations/availability",
        params={"date": saturday.isoformat(), "time": "01:30", "party_size": 2},
    )
    assert "Request failed (400)" in closed


def test_in_process_reservation_validation_matches_api(monkeypatch):
    def unavailable(*args, **kwargs):
        raise requests.ConnectionError("unavailable")

    monkeypatch.setattr(tools.requests, "request", unavailable)
    result = tools._call_api("POST", "/reservations", json={
        "name": "Test Guest", "phone": "9876543210", "date": next_weekday(2).isoformat(),
        "time": "20:00", "party_size": 11,
    })
    assert "Request failed (400)" in result
    assert "limited to 10 guests" in result
