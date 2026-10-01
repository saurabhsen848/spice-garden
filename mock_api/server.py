"""FastAPI adapter for the shared Spice Garden mock backend services.

Run with: uvicorn mock_api.server:app --port 8000
Interactive docs: http://127.0.0.1:8000/docs
"""

from datetime import date, time

from fastapi import FastAPI, HTTPException

from mock_api import services

ORDERS_FILE = services.ORDERS_FILE
RESERVATIONS_FILE = services.RESERVATIONS_FILE
TABLES_PER_SLOT = services.TABLES_PER_SLOT
MAX_PARTY_SIZE = services.MAX_PARTY_SIZE
MAX_DAYS_AHEAD = services.MAX_DAYS_AHEAD
WEEKDAY_SESSIONS = services.WEEKDAY_SESSIONS
WEEKEND_SESSIONS = services.WEEKEND_SESSIONS
ReservationRequest = services.ReservationRequest
_valid_slots = services.valid_slots

app = FastAPI(title="Spice Garden Mock API", version="1.0")


def _api_call(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except services.ServiceError as exc:
        raise HTTPException(exc.status_code, exc.detail) from exc


def _validate_slot(day: date, slot: time, party_size: int) -> None:
    return _api_call(services.validate_slot, day, slot, party_size)


def _booked_tables(day: date, slot: time) -> int:
    return services.booked_tables(day, slot, RESERVATIONS_FILE)


@app.get("/")
def root():
    return {"service": "Spice Garden Mock API", "status": "ok"}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    return _api_call(services.get_order, order_id, ORDERS_FILE)


@app.get("/reservations/availability")
def check_availability(date: date, time: time, party_size: int):
    return _api_call(services.check_availability, date, time, party_size, RESERVATIONS_FILE)


@app.post("/reservations", status_code=201)
def create_reservation(req: ReservationRequest):
    return _api_call(services.create_reservation, req, RESERVATIONS_FILE)


@app.get("/reservations/{reservation_id}")
def get_reservation(reservation_id: str):
    return _api_call(services.get_reservation, reservation_id, RESERVATIONS_FILE)
