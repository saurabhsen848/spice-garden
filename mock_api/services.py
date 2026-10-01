"""Shared business rules for the FastAPI mock service and Streamlit fallback."""

import json
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path
from threading import RLock

from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).parent
ORDERS_FILE = BASE_DIR / "orders.json"
RESERVATIONS_FILE = BASE_DIR / "reservations.json"

TABLES_PER_SLOT = 10
MAX_PARTY_SIZE = 10
MAX_DAYS_AHEAD = 30
WEEKDAY_SESSIONS = [(time(11, 0), time(0, 0))]
WEEKEND_SESSIONS = [(time(11, 0), time(2, 0))]
_reservation_lock = RLock()


class ServiceError(Exception):
    """Expected API-style error with an HTTP status and safe detail payload."""

    def __init__(self, status_code: int, detail):
        self.status_code = status_code
        self.detail = detail
        super().__init__(str(detail))


class ReservationRequest(BaseModel):
    name: str = Field(min_length=2)
    phone: str = Field(min_length=10, max_length=15)
    date: date
    time: time
    party_size: int = Field(ge=1)


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_reservations(data: dict, path: Path = RESERVATIONS_FILE) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def backend_available() -> bool:
    """Whether local bundled data needed by the in-process backend is readable."""
    try:
        load_json(ORDERS_FILE, {})
        load_json(RESERVATIONS_FILE, {})
        return True
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def valid_slots(day: date) -> list[time]:
    """Half-hour slots on a date, including an open prior-day overnight session."""
    slots = []
    for session_day in (day - timedelta(days=1), day):
        sessions = WEEKEND_SESSIONS if session_day.weekday() >= 5 else WEEKDAY_SESSIONS
        for open_time, close_time in sessions:
            opens = datetime.combine(session_day, open_time)
            close_day = session_day + timedelta(days=1) if close_time <= open_time else session_day
            closes = datetime.combine(close_day, close_time)
            current = opens
            while current < closes:
                if current.date() == day:
                    slots.append(current.time())
                current += timedelta(minutes=30)
    return sorted(set(slots))


def validate_slot(day: date, slot: time, party_size: int) -> None:
    """Apply the same time window, advance booking, and party-size rules to every backend."""
    today = date.today()
    if day < today or (day == today and slot <= datetime.now().time()):
        raise ServiceError(400, "The requested date/time is in the past.")
    if day > today + timedelta(days=MAX_DAYS_AHEAD):
        raise ServiceError(400, f"Reservations can only be made up to {MAX_DAYS_AHEAD} days in advance.")
    if not 1 <= party_size <= MAX_PARTY_SIZE:
        if party_size > MAX_PARTY_SIZE:
            detail = (f"Online reservations are limited to {MAX_PARTY_SIZE} guests. "
                      "Please call +91 80 4567 8900 for group bookings.")
        else:
            detail = "Party size must be at least 1 guest."
        raise ServiceError(400, detail)
    slots = valid_slots(day)
    if slot not in slots:
        raise ServiceError(
            400,
            "That time is not a valid reservation slot. Valid slots on this day: "
            + ", ".join(value.strftime("%I:%M %p") for value in slots),
        )


def get_order(order_id: str, path: Path = ORDERS_FILE) -> dict:
    normalized = order_id.strip().upper()
    order = load_json(path, {}).get(normalized)
    if order is None:
        raise ServiceError(404, f"No order found with ID {order_id}.")
    return {"order_id": normalized, **order}


def booked_tables(day: date, slot: time, path: Path = RESERVATIONS_FILE) -> int:
    reservations = load_json(path, {})
    return sum(
        1 for reservation in reservations.values()
        if reservation["date"] == day.isoformat() and reservation["time"] == slot.strftime("%H:%M")
    )


def check_availability(day: date, slot: time, party_size: int,
                       path: Path = RESERVATIONS_FILE) -> dict:
    validate_slot(day, slot, party_size)
    free = TABLES_PER_SLOT - booked_tables(day, slot, path)
    return {"date": day.isoformat(), "time": slot.strftime("%H:%M"), "party_size": party_size,
            "available": free > 0, "tables_left": max(free, 0)}


def create_reservation(request: ReservationRequest, path: Path = RESERVATIONS_FILE) -> dict:
    validate_slot(request.date, request.time, request.party_size)
    with _reservation_lock:
        reservations = load_json(path, {})
        booked = sum(
            1 for reservation in reservations.values()
            if reservation["date"] == request.date.isoformat()
            and reservation["time"] == request.time.strftime("%H:%M")
        )
        if booked >= TABLES_PER_SLOT:
            raise ServiceError(409, "Sorry, this slot is fully booked. Please choose another time.")

        reservation_id = f"RES-{random.randint(1000, 9999)}"
        while reservation_id in reservations:
            reservation_id = f"RES-{random.randint(1000, 9999)}"
        reservation = {
            "name": request.name, "phone": request.phone, "date": request.date.isoformat(),
            "time": request.time.strftime("%H:%M"), "party_size": request.party_size,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        reservations[reservation_id] = reservation
        save_reservations(reservations, path)
    return {"reservation_id": reservation_id, "status": "confirmed", **reservation}


def get_reservation(reservation_id: str, path: Path = RESERVATIONS_FILE) -> dict:
    normalized = reservation_id.strip().upper()
    reservation = load_json(path, {}).get(normalized)
    if reservation is None:
        raise ServiceError(404, f"No reservation found with ID {reservation_id}.")
    return {"reservation_id": normalized, **reservation}
