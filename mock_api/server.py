"""Mock restaurant backend API for Spice Garden.

Simulates the restaurant's order-tracking and table-reservation services.
Run with:  uvicorn mock_api.server:app --port 8000
Interactive docs: http://127.0.0.1:8000/docs
"""

import json
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).parent
ORDERS_FILE = BASE_DIR / "orders.json"
RESERVATIONS_FILE = BASE_DIR / "reservations.json"

TABLES_PER_SLOT = 10
MAX_PARTY_SIZE = 10
MAX_DAYS_AHEAD = 30

# (open, close) sessions per opening day; close times earlier than open times are next-day closes.
# Must match data/policies.md. Weekdays close at midnight; weekends close at 2 AM next day.
WEEKDAY_SESSIONS = [(time(11, 0), time(0, 0))]
WEEKEND_SESSIONS = [(time(11, 0), time(2, 0))]

app = FastAPI(title="Spice Garden Mock API", version="1.0")


class ReservationRequest(BaseModel):
    name: str = Field(min_length=2)
    phone: str = Field(min_length=10, max_length=15)
    date: date
    time: time
    party_size: int = Field(ge=1)


# ---------- helpers ----------

def _load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save_reservations(data: dict) -> None:
    RESERVATIONS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _valid_slots(day: date) -> list[time]:
    """Return half-hour slots on this calendar day, including an open prior-day overnight session."""
    slots = []
    for session_day in (day - timedelta(days=1), day):
        sessions = WEEKEND_SESSIONS if session_day.weekday() >= 5 else WEEKDAY_SESSIONS
        for open_t, close_t in sessions:
            opens = datetime.combine(session_day, open_t)
            close_day = session_day + timedelta(days=1) if close_t <= open_t else session_day
            closes = datetime.combine(close_day, close_t)
            current = opens
            while current < closes:
                if current.date() == day:
                    slots.append(current.time())
                current += timedelta(minutes=30)
    return sorted(set(slots))


def _validate_slot(day: date, slot: time, party_size: int) -> None:
    """Raise HTTP 400 with a readable reason if the booking breaks a policy."""
    today = date.today()
    if day < today or (day == today and slot <= datetime.now().time()):
        raise HTTPException(400, "The requested date/time is in the past.")
    if day > today + timedelta(days=MAX_DAYS_AHEAD):
        raise HTTPException(400, f"Reservations can only be made up to {MAX_DAYS_AHEAD} days in advance.")
    if party_size > MAX_PARTY_SIZE:
        raise HTTPException(400, f"Online reservations are limited to {MAX_PARTY_SIZE} guests. "
                                 "Please call +91 80 4567 8900 for group bookings.")
    slots = _valid_slots(day)
    if slot not in slots:
        raise HTTPException(400, "That time is not a valid reservation slot. Valid slots on this day: "
                                 + ", ".join(s.strftime("%I:%M %p") for s in slots))


def _booked_tables(day: date, slot: time) -> int:
    reservations = _load_json(RESERVATIONS_FILE, {})
    return sum(1 for r in reservations.values()
               if r["date"] == day.isoformat() and r["time"] == slot.strftime("%H:%M"))


# ---------- endpoints ----------

@app.get("/")
def root():
    return {"service": "Spice Garden Mock API", "status": "ok"}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    orders = _load_json(ORDERS_FILE, {})
    order = orders.get(order_id.strip().upper())
    if order is None:
        raise HTTPException(404, f"No order found with ID {order_id}.")
    return {"order_id": order_id.strip().upper(), **order}


@app.get("/reservations/availability")
def check_availability(date: date, time: time, party_size: int):
    _validate_slot(date, time, party_size)
    free = TABLES_PER_SLOT - _booked_tables(date, time)
    return {"date": date.isoformat(), "time": time.strftime("%H:%M"), "party_size": party_size,
            "available": free > 0, "tables_left": max(free, 0)}


@app.post("/reservations", status_code=201)
def create_reservation(req: ReservationRequest):
    _validate_slot(req.date, req.time, req.party_size)
    if _booked_tables(req.date, req.time) >= TABLES_PER_SLOT:
        raise HTTPException(409, "Sorry, this slot is fully booked. Please choose another time.")

    reservations = _load_json(RESERVATIONS_FILE, {})
    res_id = f"RES-{random.randint(1000, 9999)}"
    while res_id in reservations:
        res_id = f"RES-{random.randint(1000, 9999)}"

    reservations[res_id] = {
        "name": req.name, "phone": req.phone, "date": req.date.isoformat(),
        "time": req.time.strftime("%H:%M"), "party_size": req.party_size,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    _save_reservations(reservations)
    return {"reservation_id": res_id, "status": "confirmed", **reservations[res_id]}


@app.get("/reservations/{reservation_id}")
def get_reservation(reservation_id: str):
    reservations = _load_json(RESERVATIONS_FILE, {})
    res = reservations.get(reservation_id.strip().upper())
    if res is None:
        raise HTTPException(404, f"No reservation found with ID {reservation_id}.")
    return {"reservation_id": reservation_id.strip().upper(), **res}
