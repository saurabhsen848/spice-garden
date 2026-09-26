from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from mock_api import server

client = TestClient(server.app)


@pytest.fixture(autouse=True)
def temp_reservations(tmp_path, monkeypatch):
    """Use a throwaway reservations file so tests never touch real data."""
    monkeypatch.setattr(server, "RESERVATIONS_FILE", tmp_path / "reservations.json")


def next_weekday(weekday: int) -> date:
    """Next date (at least tomorrow) falling on the given weekday (Mon=0)."""
    d = date.today() + timedelta(days=1)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


def booking(**overrides):
    body = {"name": "Test User", "phone": "9876543210",
            "date": next_weekday(2).isoformat(), "time": "20:00", "party_size": 4}
    body.update(overrides)
    return body


def test_get_existing_order():
    r = client.get("/orders/ord1003")
    assert r.status_code == 200
    assert r.json()["status"] == "Preparing"


def test_get_missing_order():
    assert client.get("/orders/ORD9999").status_code == 404


def test_availability_ok():
    r = client.get("/reservations/availability",
                   params={"date": next_weekday(2).isoformat(), "time": "20:00", "party_size": 2})
    assert r.status_code == 200
    assert r.json()["tables_left"] == server.TABLES_PER_SLOT


def test_create_and_fetch_reservation():
    r = client.post("/reservations", json=booking())
    assert r.status_code == 201
    res_id = r.json()["reservation_id"]
    assert client.get(f"/reservations/{res_id}").json()["party_size"] == 4


@pytest.mark.parametrize("overrides", [
    {"time": "03:00"},                                                  # restaurant closed
    {"time": "16:00"},                                                  # weekday afternoon break
    {"time": "22:30"},                                                  # after last weekday slot
    {"party_size": 50},                                                 # too large
    {"date": (date.today() - timedelta(days=1)).isoformat()},           # past
    {"date": (date.today() + timedelta(days=45)).isoformat()},          # too far ahead
])
def test_policy_violations_rejected(overrides):
    assert client.post("/reservations", json=booking(**overrides)).status_code == 400


def test_weekend_afternoon_allowed():
    r = client.post("/reservations", json=booking(date=next_weekday(5).isoformat(), time="16:00"))
    assert r.status_code == 201


def test_slot_fills_up():
    for _ in range(server.TABLES_PER_SLOT):
        assert client.post("/reservations", json=booking()).status_code == 201
    assert client.post("/reservations", json=booking()).status_code == 409
