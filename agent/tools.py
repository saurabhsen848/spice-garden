"""Tools the agent can call. Docstrings are sent to the LLM, so they explain *when* to use each tool."""

import json
from datetime import date, time
from typing import Literal, Optional

import requests
from langchain_core.tools import tool
from pydantic import ValidationError

from agent import config
from agent.rag import dish_to_text, load_menu, retrieve
from mock_api import services

Category = Literal["Starters", "Mains", "Breads", "Desserts", "Beverages"]
API_DOWN = ("The restaurant's order/reservation system is currently unreachable. "
            "Apologise and ask the customer to call +91 80 4567 8900.")


def _format_api_error(status_code: int, detail) -> str:
    if isinstance(detail, list):
        detail = "; ".join(
            f"{'.'.join(map(str, error.get('loc', [])[1:]))}: {error.get('msg', 'Invalid value')}"
            for error in detail
        )
    return f"Request failed ({status_code}): {detail}"


def _in_process_call(method: str, path: str, *, params=None, json_body=None) -> dict | str:
    """Fallback to bundled mock data while sharing FastAPI's service rules."""
    try:
        if method == "GET" and path.startswith("/orders/"):
            return services.get_order(path.rsplit("/", 1)[-1], services.ORDERS_FILE)
        if method == "GET" and path == "/reservations/availability":
            params = params or {}
            try:
                day = date.fromisoformat(str(params["date"]))
                slot = time.fromisoformat(str(params["time"]))
                party_size = int(params["party_size"])
            except (KeyError, TypeError, ValueError):
                return _format_api_error(422, "Invalid date, time, or party_size.")
            return services.check_availability(day, slot, party_size, services.RESERVATIONS_FILE)
        if method == "POST" and path == "/reservations":
            try:
                request = services.ReservationRequest.model_validate(json_body or {})
            except ValidationError as exc:
                return _format_api_error(422, exc.errors(include_url=False))
            return services.create_reservation(request, services.RESERVATIONS_FILE)
        if method == "GET" and path.startswith("/reservations/"):
            return services.get_reservation(path.rsplit("/", 1)[-1], services.RESERVATIONS_FILE)
        return _format_api_error(404, "Not found")
    except services.ServiceError as exc:
        return _format_api_error(exc.status_code, exc.detail)
    except (OSError, json.JSONDecodeError, TypeError, KeyError):
        return API_DOWN


def _call_api(method: str, path: str, **kwargs) -> dict | str:
    """Prefer the configured API; use the shared in-process service if it is unavailable."""
    try:
        resp = requests.request(method, f"{config.API_BASE_URL}{path}", timeout=4, **kwargs)
    except requests.RequestException:
        return _in_process_call(method, path, params=kwargs.get("params"), json_body=kwargs.get("json"))
    if resp.ok:
        try:
            return resp.json()
        except requests.RequestException:
            return API_DOWN
    try:
        detail = resp.json().get("detail", resp.text)
    except requests.RequestException:
        detail = resp.text or "The configured backend returned an unreadable response."
    return _format_api_error(resp.status_code, detail)


def backend_mode() -> str:
    """Return connected, cloud, or offline for the sidebar service indicator."""
    try:
        response = requests.get(config.API_BASE_URL, timeout=2)
        if response.ok:
            return "connected"
    except requests.RequestException:
        pass
    return "cloud" if services.backend_available() else "offline"


# ---------------- RAG tools ----------------

@tool
def search_menu(query: str) -> str:
    """Search the Spice Garden menu for specific dishes, ingredients, prices, spice levels or allergens.
    Use for questions like 'do you have biryani?', 'is paneer tikka spicy?', 'which dishes contain nuts?'."""
    docs = retrieve(query, kind="menu", k=5)
    return "\n".join(f"- {d.page_content}" for d in docs)


@tool
def browse_menu(category: Optional[Category] = None) -> str:
    """List the full menu, or all dishes in one category. Use when the customer wants to see the menu."""
    dishes = [d for d in load_menu() if category is None or d["category"] == category]
    lines, current = [], None
    for d in dishes:
        if d["category"] != current:
            current = d["category"]
            lines.append(f"\n## {current}")
        tag = "Veg" if d["veg"] else "Non-veg"
        lines.append(f"- {d['name']} - Rs.{d['price']} ({tag}, spice {d['spice']}/3)")
    return "\n".join(lines).strip()


@tool
def recommend_dishes(
    veg_only: bool = False,
    max_spice: Optional[int] = None,
    max_price: Optional[int] = None,
    exclude_allergens: Optional[list[str]] = None,
    category: Optional[Category] = None,
) -> str:
    """Find dishes matching the customer's preferences, for personalised recommendations.
    Args:
        veg_only: only vegetarian dishes.
        max_spice: maximum spice level, 0 (not spicy) to 3 (hot).
        max_price: maximum price per dish in rupees.
        exclude_allergens: allergens to avoid, from: dairy, nuts, gluten, soy, fish.
        category: restrict to one menu category.
    Pick the best 2-4 from the results and explain briefly why each suits the customer."""
    avoid = {a.lower().strip() for a in (exclude_allergens or [])}
    matches = [
        d for d in load_menu()
        if (not veg_only or d["veg"])
        and (max_spice is None or d["spice"] <= max_spice)
        and (max_price is None or d["price"] <= max_price)
        and (category is None or d["category"] == category)
        and not avoid.intersection(d["allergens"])
    ]
    if not matches:
        return "No dishes match all of these preferences. Suggest relaxing one of them."
    return "\n".join(f"- {dish_to_text(d)}" for d in matches)


@tool
def search_restaurant_info(query: str) -> str:
    """Search Spice Garden's policies and FAQs: opening hours, location, contact, parking, reservation
    and cancellation rules, delivery, payment, allergy policy, offers, events, facilities."""
    docs = retrieve(query, kind="info", k=3)
    return "\n\n".join(f"[{d.metadata['source']}] {d.page_content}" for d in docs)


# ---------------- API tools ----------------

@tool
def check_order_status(order_id: str) -> str:
    """Get the live status of an existing food order by its order ID (format ORD followed by digits, e.g. ORD1003)."""
    return str(_call_api("GET", f"/orders/{order_id.strip()}"))


@tool
def check_table_availability(date: str, time: str, party_size: int) -> str:
    """Check if a table is free. date as YYYY-MM-DD, time as 24-hour HH:MM (e.g. 20:00), party_size = number of guests."""
    result = _call_api("GET", "/reservations/availability",
                       params={"date": date, "time": time, "party_size": party_size})
    if isinstance(result, dict) and result["available"]:
        # Steer the model: booking is a real action, so the customer must approve the details first.
        return (f"{result}\nNEXT STEP: collect any missing name/phone, then read ALL booking details back "
                "and ask the customer to confirm. Do NOT call make_reservation until they reply yes.")
    return str(result)


@tool
def make_reservation(name: str, phone: str, date: str, time: str, party_size: int) -> str:
    """Book a table. Only call this after you have read the full details (name, phone, date, time, party size)
    back to the customer AND they explicitly confirmed in their latest message. Receiving the name and phone
    is NOT a confirmation. date as YYYY-MM-DD, time as 24-hour HH:MM."""
    return str(_call_api("POST", "/reservations", json={
        "name": name, "phone": phone, "date": date, "time": time, "party_size": party_size}))


ALL_TOOLS = [search_menu, browse_menu, recommend_dishes, search_restaurant_info,
             check_order_status, check_table_availability, make_reservation]
