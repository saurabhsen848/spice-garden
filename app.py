"""Spice Garden restaurant chat agent - Streamlit UI.

Run: streamlit run app.py (start the mock API first: uvicorn mock_api.server:app --port 8000)
"""

import html
import json
import logging

import streamlit as st

from agent import config
from agent.agent import build_agent, chat
from agent.diagnostics import safe_exception_traceback
from agent.tools import backend_mode

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Spice Garden | AI Restaurant Assistant",
    page_icon=":material/local_dining:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Friendly labels for the real tool calls shown under each reply.
TOOL_LABELS = {
    "search_menu": ":material/search: Searched the restaurant menu",
    "browse_menu": ":material/menu_book: Browsed the menu",
    "recommend_dishes": ":material/thumb_up: Filtered dish recommendations",
    "search_restaurant_info": ":material/info: Searched restaurant information",
    "check_order_status": ":material/local_shipping: Checked order status",
    "check_table_availability": ":material/event_available: Checked table availability",
    "make_reservation": ":material/event_seat: Created a reservation",
}

SUGGESTIONS = {
    ":material/menu_book: View Menu": "Show me the full menu",
    ":material/thumb_up: Recommend a Dish": "Can you recommend a vegetarian dish that is not too spicy?",
    ":material/local_shipping: Track Order": "I want to track my order ORD1002",
    ":material/event_seat: Book a Table": "I'd like to book a table",
    ":material/schedule: Opening Hours": "What are your opening hours and where are you located?",
}

ACTION_CARDS = [
    ("🍽", "Explore the menu", "Browse dishes, prices and categories.", ":material/menu_book: View Menu"),
    ("✦", "Recommend a dish", "Get a dish recommendation made for you.", ":material/thumb_up: Recommend a Dish"),
    ("↗", "Track Order", "Get an update on an existing order.", ":material/local_shipping: Track Order"),
    ("◷", "Book a Table", "Start a reservation with our assistant.", ":material/event_seat: Book a Table"),
]

MENU_CATEGORIES = ["Starters", "Mains", "Breads", "Desserts", "Beverages"]


def apply_styles() -> None:
    st.markdown(
        """<style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');
        :root { --sg-ink:#2b211b; --sg-muted:#78695e; --sg-cream:#fbf7f0; --sg-paper:#fffdf9;
                --sg-saffron:#d76b2c; --sg-line:#eadfd2; --sg-green:#42745a; }
        html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
        .stApp { background:radial-gradient(ellipse at 72% 0%, #f4e6d5 0, transparent 38%), var(--sg-cream); color:var(--sg-ink); }
        [data-testid="stHeader"] { background:rgba(251,247,240,.78); }
        [data-testid="stSidebar"] { background:linear-gradient(180deg,#2d211b 0%,#38271e 100%); border-right:1px solid #4b3629; }
        [data-testid="stSidebar"] * { color:#f8efe4; }
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color:#e3d5c6; }
        [data-testid="stSidebar"] hr { border-color:#604636; }
        [data-testid="stSidebar"] [data-testid="stButton"] button { background:#493429; border:1px solid #614737; color:#fff7ed; border-radius:12px; min-height:2.8rem; text-align:left; transition:all .18s ease; }
        [data-testid="stSidebar"] [data-testid="stButton"] button:hover { background:#62432f; border-color:#d78a4e; transform:translateY(-1px); }
        [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"] { background:#c85f28; }
        main .block-container,[data-testid="stMainBlockContainer"] { max-width:none!important;width:100%!important;box-sizing:border-box;padding:clamp(1.1rem,2vw,2.2rem) clamp(1rem,2.4vw,3rem) 6rem;overflow-x:hidden; }
        .sg-topbar { display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:1rem 1.25rem; margin-bottom:2.1rem;
          background:rgba(255,253,249,.86); border:1px solid var(--sg-line); border-radius:20px; box-shadow:0 10px 30px rgba(64,40,23,.06); }
        .sg-brand { display:flex; align-items:center; gap:.85rem; }
        .sg-mark { width:48px;height:48px;display:grid;place-items:center;border-radius:15px;background:linear-gradient(145deg,#e7833b,#b84e20);color:#fff;font-size:24px;box-shadow:0 6px 14px #bf632f44; }
        .sg-brand-name { font:700 1.42rem 'Playfair Display',serif; letter-spacing:-.02em; color:var(--sg-ink); }
        .sg-brand-sub { color:var(--sg-muted);font-size:.83rem;margin-top:1px; }
        .sg-ready { border:1px solid #cfe1d2;background:#eff7ef;color:#376349;border-radius:999px;padding:.48rem .8rem;font-size:.8rem;font-weight:600;white-space:nowrap; }
        .sg-ready-dot { display:inline-block;width:8px;height:8px;background:#4e9a66;border-radius:50%;margin-right:.42rem;box-shadow:0 0 0 3px #4e9a6624; }
        .sg-eyebrow { color:#b45a2b;text-transform:uppercase;letter-spacing:.16em;font-size:.72rem;font-weight:700; }
        .sg-hero-title { font:700 clamp(2.15rem,5vw,3.6rem)/1.12 'Playfair Display',serif;color:#30231c;letter-spacing:-.035em;margin:.55rem 0 .8rem; }
        .sg-hero-copy { color:#75665b;font-size:1.05rem;max-width:780px;line-height:1.7;margin:0 auto 1rem; }
        .sg-hero { width:100%;padding:1.1rem .25rem .65rem;text-align:center; }
        [class*="st-key-hero_card_"] { height:100%;min-height:286px;box-sizing:border-box;padding:1rem;background:linear-gradient(145deg,#fffefa,#f8efe4);border:1px solid #eadbc9;border-radius:18px;box-shadow:0 8px 22px rgba(73,46,27,.055);transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease;overflow:hidden; }
        [class*="st-key-hero_card_"]:hover { transform:translateY(-3px);border-color:#dca477;box-shadow:0 13px 28px rgba(73,46,27,.12); }
        [class*="st-key-hero_card_"] [data-testid="stVerticalBlock"] { height:100%;display:flex;flex-direction:column;gap:.55rem; }
        [class*="st-key-hero_card_"] [data-testid="stElementContainer"]:has(button) { margin-top:auto; }
        .sg-card-content { min-height:154px;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;text-align:center;overflow-wrap:anywhere; }
        .sg-card-icon { width:39px;height:39px;display:grid;place-items:center;background:#fae8d6;border-radius:12px;color:#b95727;font-size:20px;margin:0 auto .75rem; }
        .sg-card-title { font-weight:700;color:#34271f;font-size:.97rem;margin-bottom:.3rem;text-align:center; }
        .sg-card-copy { color:#817267;font-size:.82rem;line-height:1.5;text-align:center;max-width:15rem; }
        [class*="st-key-hero_card_"] [data-testid="stButton"] button { width:100%;min-height:2.8rem;border-radius:12px;background:#f7e8d8;border:1px solid #edd4bd;color:#9f4f28;font-weight:650; }
        [class*="st-key-hero_card_"] [data-testid="stButton"] button:hover { background:#f2dcc5;border-color:#d99769;color:#78391c; }
        [data-testid="stChatMessage"] { border:1px solid #eee2d5;border-radius:20px;padding:.9rem 1rem;background:#fffdf9;box-shadow:0 5px 18px rgba(65,43,26,.045);margin:.8rem 0; }
        [data-testid="stChatMessage"] [data-testid="stMarkdownContainer"] { font-size:1rem;line-height:1.7;color:#392d25;overflow-wrap:anywhere;word-break:normal;max-width:100%; }
        [data-testid="stChatMessage"] h1,[data-testid="stChatMessage"] h2,[data-testid="stChatMessage"] h3 { font-family:'Playfair Display',serif;color:#493326;line-height:1.3;overflow-wrap:anywhere; }
        [data-testid="stChatMessage"] h2 { font-size:1.28rem;margin:1.15rem 0 .45rem;padding-bottom:.35rem;border-bottom:1px solid #eee1d3; }
        [data-testid="stChatMessage"] h3 { font-size:1.08rem;margin:1rem 0 .35rem; }
        [data-testid="stChatMessage"] ul,[data-testid="stChatMessage"] ol { padding-left:1.45rem;margin:.45rem 0 .9rem; }
        [data-testid="stChatMessage"] li { margin:.26rem 0;line-height:1.65; }
        [data-testid="stChatMessage"] pre,[data-testid="stChatMessage"] table { max-width:100%;overflow-x:auto; }
        [data-testid="stChatMessage"] [data-testid="stChatMessageAvatarAssistant"] { background:#f5e5d5;border-radius:50%; }
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) { background:#3b2a20;border-color:#3b2a20;margin-left:12%; }
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stMarkdownContainer"] { color:#fff8f0; }
        [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageAvatarUser"] { background:#68442f;border-radius:50%; }
        [data-testid="stChatInput"] { border:0!important;border-radius:20px!important;background:#fffefa!important;box-shadow:0 10px 32px rgba(57,38,24,.14),0 0 0 1px #eadfd2; }
        [data-testid="stChatInput"] textarea { font-size:1rem!important;line-height:1.5!important; }
        [data-testid="stChatInput"]:focus-within { box-shadow:0 0 0 2px #cf7541,0 12px 34px rgba(57,38,24,.15)!important; }
        [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stChatMessage"]) { border:0!important;box-shadow:none!important;background:transparent!important; }
        [data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stChatMessage"]) > div { scrollbar-color:#c6a88d transparent;scrollbar-width:thin; }
        [data-testid="stExpander"] summary { font-weight:650!important;color:#574233!important; }
        [data-testid="stStatusWidget"] { border:1px solid #eadbc9;border-radius:11px;background:#fffaf3; }
        [data-testid="stButton"] button { border-radius:12px;min-height:2.8rem;transition:all .18s ease; }
        .stButton button:hover { transform:translateY(-1px);box-shadow:0 5px 14px rgba(66,41,23,.12); }
        [data-testid="stExpander"] { background:#faf4ec;border:1px solid #eadbc9;border-radius:14px;overflow:hidden; }
        .sg-section-label { color:#a9927e;font-size:.7rem;font-weight:700;letter-spacing:.13em;text-transform:uppercase;margin:.95rem 0 .3rem; }
        .sg-menu-intro { display:flex;align-items:flex-end;justify-content:space-between;gap:1rem;margin:.35rem 0 1rem; }
        .sg-menu-hero { padding:.8rem .2rem .4rem;margin-bottom:.55rem; }
        .sg-menu-hero h1 { font:700 clamp(2rem,4vw,3.25rem)/1.15 'Playfair Display',serif;color:#30231c;margin:.45rem 0 .6rem; }
        .sg-menu-hero p { color:#75665b;font-size:1rem;line-height:1.65;max-width:800px;margin:0 0 1rem; }
        .sg-menu-title { font:700 clamp(1.45rem,2.5vw,2rem)/1.2 'Playfair Display',serif;color:#30231c; }
        .sg-menu-count { color:#857568;font-size:.85rem; }
        .sg-menu-grid { display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;width:100%; }
        .sg-menu-card { display:flex;flex-direction:column;min-width:0;min-height:238px;padding:1.05rem 1.05rem .95rem;background:linear-gradient(145deg,#fffefa,#f8efe4);border:1px solid #eadbc9;border-radius:17px;box-shadow:0 7px 20px rgba(73,46,27,.055);transition:transform .18s ease,box-shadow .18s ease,border-color .18s ease;overflow-wrap:anywhere; }
        .sg-menu-card:hover { transform:translateY(-3px);border-color:#dca477;box-shadow:0 13px 26px rgba(73,46,27,.12); }
        .sg-menu-card-top { display:flex;align-items:flex-start;justify-content:space-between;gap:.6rem; }
        .sg-menu-name { font-weight:700;font-size:1rem;line-height:1.35;color:#34271f; }
        .sg-menu-price { flex:none;color:#ad5429;font-weight:700;font-size:1rem;white-space:nowrap; }
        .sg-menu-tags { display:flex;flex-wrap:wrap;gap:.4rem;margin:.75rem 0 .65rem; }
        .sg-menu-tag { display:inline-flex;align-items:center;border-radius:999px;padding:.25rem .55rem;background:#f5eadd;color:#76533c;font-size:.72rem;font-weight:600; }
        .sg-menu-tag.veg { background:#e7f1e6;color:#416a49; }
        .sg-menu-tag.nonveg { background:#f7e5df;color:#995039; }
        .sg-menu-description { color:#78695e;font-size:.84rem;line-height:1.55;flex:1; }
        .sg-menu-allergens { margin-top:.75rem;padding-top:.6rem;border-top:1px solid #eee2d5;color:#8a7869;font-size:.74rem;line-height:1.4; }
        @media(max-width:1150px) { .sg-menu-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
        @media(max-width:620px) { .sg-menu-grid { grid-template-columns:minmax(0,1fr);gap:.7rem; }.sg-menu-card { min-height:0; } }
        @media(max-width:700px) { .block-container{padding:1rem .75rem 6rem}.sg-topbar{padding:.8rem;border-radius:16px;margin-bottom:1.25rem;flex-wrap:wrap}.sg-ready{font-size:.7rem;padding:.4rem .55rem}.sg-brand-name{font-size:1.15rem}.sg-mark{width:42px;height:42px}[class*="st-key-hero_card_"]{min-height:258px;padding:.85rem}.sg-card-content{min-height:138px}.sg-hero-copy{font-size:.96rem}[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){margin-left:4%}[data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:.65rem}[data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{min-width:min(100%,230px);flex:1 1 45%} }
        </style>""",
        unsafe_allow_html=True,
    )


@st.cache_resource(ttl=3600)  # rebuilt hourly so today's date in the system prompt stays correct
def get_agent():
    return build_agent()


@st.cache_data(show_spinner=False)
def load_menu_data() -> list[dict]:
    """Read the same menu JSON used by the restaurant tools and RAG index."""
    return json.loads(config.MENU_FILE.read_text(encoding="utf-8"))


def render_menu_cards(tool_calls: list[dict], widget_key: str) -> None:
    """Render menu cards using the shared menu data source."""
    menu = load_menu_data()
    browse_call = next((call for call in reversed(tool_calls) if call.get("name") == "browse_menu"), {})
    requested_category = (browse_call.get("args") or {}).get("category")
    default_category = requested_category if requested_category in MENU_CATEGORIES else "All"

    categories = ["All", *dict.fromkeys(str(dish.get("category", "")) for dish in menu if dish.get("category"))]
    selected_category = st.pills(
        "Menu category",
        categories,
        default=default_category,
        key=f"menu_category_{widget_key}",
        label_visibility="collapsed",
        width="stretch",
    ) or default_category
    visible_dishes = [
        dish for dish in menu
        if selected_category == "All" or dish.get("category") == selected_category
    ]

    st.markdown(
        f"<div class='sg-menu-intro'><div class='sg-menu-title'>Our Menu</div>"
        f"<div class='sg-menu-count'>{len(visible_dishes)} of {len(menu)} dishes</div></div>",
        unsafe_allow_html=True,
    )
    cards = []
    for dish in visible_dishes:
        name = html.escape(str(dish.get("name", "")))
        price = f"₹{int(dish['price']):,}" if dish.get("price") is not None else ""
        description = html.escape(str(dish.get("description", "")))
        allergens = dish.get("allergens") or []
        allergen_text = ", ".join(html.escape(str(item).title()) for item in allergens) or "None listed"
        diet_label = "Vegetarian" if dish.get("veg") else "Non-Vegetarian"
        diet_class = "veg" if dish.get("veg") else "nonveg"
        category = html.escape(str(dish.get("category", "")))
        spice_label = f"Spice {dish['spice']}/3" if dish.get("spice") is not None else ""
        cards.append(
            "<div class='sg-menu-card'>"
            f"<div class='sg-menu-card-top'><div class='sg-menu-name'>{name}</div><div class='sg-menu-price'>{price}</div></div>"
            f"<div class='sg-menu-tags'><span class='sg-menu-tag category'>{category}</span><span class='sg-menu-tag {diet_class}'>{diet_label}</span>"
            f"<span class='sg-menu-tag'>{spice_label}</span></div>"
            f"<div class='sg-menu-description'>{description}</div>"
            f"<div class='sg-menu-allergens'>Allergens: {allergen_text}</div>"
            "</div>"
        )
    st.markdown(f"<div class='sg-menu-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_full_menu() -> None:
    """Render a filterable full-menu page from data/menu.json."""
    menu = load_menu_data()
    st.markdown(
        "<div class='sg-menu-hero'><div class='sg-eyebrow'>OUR MENU</div>"
        "<h1>Explore the flavors of Spice Garden</h1>"
        "<p>Discover our carefully prepared Indian dishes, from classic starters to rich mains, breads, desserts and refreshing beverages.</p></div>",
        unsafe_allow_html=True,
    )
    if st.button("← Back to Home", key="menu_back_home"):
        st.session_state.view = "home"
        st.rerun()

    available_categories = list(dict.fromkeys(
        str(dish.get("category")) for dish in menu if dish.get("category")
    ))
    category_order = [name for name in MENU_CATEGORIES if name in available_categories]
    category_order.extend(name for name in available_categories if name not in category_order)
    category = st.pills(
        "Category", ["All", *category_order], default="All", key="full_menu_category",
        label_visibility="collapsed", width="stretch",
    ) or "All"

    filter_cols = st.columns([2, 1, 1, 1])
    with filter_cols[0]:
        query = st.text_input("Search dishes", placeholder="Search by dish or ingredient", key="full_menu_search")
    with filter_cols[1]:
        vegetarian_only = st.checkbox("Vegetarian", key="full_menu_vegetarian")
    spice_levels = sorted({dish.get("spice") for dish in menu if isinstance(dish.get("spice"), int)})
    with filter_cols[2]:
        selected_spice = st.selectbox("Spice level", ["Any", *spice_levels], key="full_menu_spice")
    with filter_cols[3]:
        sort_order = st.selectbox("Sort by", ["Default", "Price: Low to High", "Price: High to Low", "Name: A-Z"], key="full_menu_sort")

    search_text = query.casefold().strip()
    visible = [dish for dish in menu if
        (category == "All" or dish.get("category") == category)
        and (not search_text or search_text in str(dish.get("name", "")).casefold()
             or search_text in str(dish.get("description", "")).casefold())
        and (not vegetarian_only or dish.get("veg") is True)
        and (selected_spice == "Any" or dish.get("spice") == selected_spice)
    ]
    if sort_order == "Price: Low to High":
        visible.sort(key=lambda dish: dish.get("price", float("inf")))
    elif sort_order == "Price: High to Low":
        visible.sort(key=lambda dish: dish.get("price", float("-inf")), reverse=True)
    elif sort_order == "Name: A-Z":
        visible.sort(key=lambda dish: str(dish.get("name", "")).casefold())

    st.markdown(f"<div class='sg-menu-count' style='margin:.45rem 0 1rem'>Showing {len(visible)} dishes</div>", unsafe_allow_html=True)
    if not visible:
        st.info("No dishes match those filters. Try a different search or category.")
        return

    cards = []
    for dish in visible:
        name = html.escape(str(dish.get("name", "")))
        description = html.escape(str(dish.get("description", "")))
        category_label = html.escape(str(dish.get("category", "")))
        price = f"₹{int(dish['price']):,}" if dish.get("price") is not None else ""
        veg = dish.get("veg")
        diet = "Vegetarian" if veg is True else "Non-Vegetarian" if veg is False else ""
        diet_class = "veg" if veg is True else "nonveg"
        spice = f"Spice {dish['spice']}/3" if dish.get("spice") is not None else ""
        tags = "".join(
            f"<span class='sg-menu-tag {css_class}'>{html.escape(label)}</span>"
            for label, css_class in ((category_label, "category"), (diet, diet_class), (spice, "")) if label
        )
        allergen_items = dish.get("allergens")
        allergen_html = ""
        if isinstance(allergen_items, list):
            allergen_text = ", ".join(html.escape(str(item).title()) for item in allergen_items) or "None listed"
            allergen_html = f"<div class='sg-menu-allergens'>Allergens: {allergen_text}</div>"
        cards.append(
            "<div class='sg-menu-card'><div class='sg-menu-card-top'>"
            f"<div class='sg-menu-name'>{name}</div><div class='sg-menu-price'>{price}</div></div>"
            f"<div class='sg-menu-tags'>{tags}</div><div class='sg-menu-description'>{description}</div>{allergen_html}</div>"
        )
    st.markdown(f"<div class='sg-menu-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_tool_steps(tools: list[dict]) -> None:
    """Collapsed activity panel with the actual tools and arguments for this reply."""
    if not tools:
        return
    with st.expander(f":material/settings: AI activity · {len(tools)} {('step' if len(tools) == 1 else 'steps')}", expanded=False):
        for tool_call in tools:
            with st.status(TOOL_LABELS.get(tool_call["name"], tool_call["name"]), state="complete", expanded=False):
                st.code(f"{tool_call['name']}({json.dumps(tool_call['args'], ensure_ascii=False)})", language="python")


def queue_prompt(prompt: str) -> None:
    st.session_state.pending = prompt


apply_styles()

# ---------------- session state ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # display messages: {role, content, tools}
    st.session_state.history = []   # LangChain messages: the agent's conversation memory
    st.session_state.pending = None
if "view" not in st.session_state:
    st.session_state.view = "home"

order_backend_mode = backend_mode()

# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown("<div style='padding:.7rem 0 1rem'><div style='font:700 1.45rem Playfair Display,serif;color:#fff7ed;letter-spacing:.04em'>SPICE GARDEN</div><div style='color:#d9c7b6;font-size:.84rem;margin-top:.18rem'>Multi-cuisine Indian Restaurant</div><div style='color:#bca792;font-size:.82rem;margin-top:.5rem'>&#9679; &nbsp;MG Road, Bengaluru</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='sg-section-label'>Restaurant details</div>", unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(
            "**:material/schedule: Opening Hours**  \n\n"
            "**Mon–Fri**  \n11:00 AM – 12:00 AM  \n\n"
            "**Sat–Sun**  \n11:00 AM – 2:00 AM  \n\n"
            "**:material/call: Phone**  \n+91 8969700172  \n\n"
            "**:material/location_on: Location**  \nMG Road, Bengaluru"
        )

    st.markdown("<div class='sg-section-label'>Quick actions</div>", unsafe_allow_html=True)
    for label, prompt in SUGGESTIONS.items():
        if st.button(label, key=f"sidebar_{label}", width="stretch"):
            if label == ":material/menu_book: View Menu":
                st.session_state.view = "menu"
            else:
                st.session_state.view = "home"
                queue_prompt(prompt)
            st.rerun()

    st.markdown("<div class='sg-section-label'>System status</div>", unsafe_allow_html=True)
    if order_backend_mode == "connected":
        status_text, status_colors = "Order &amp; Booking API: Connected", ("#45674f", "#344d3b", "#dff1df", "#80cf8f")
    elif order_backend_mode == "cloud":
        status_text, status_colors = "Order &amp; Booking: Cloud Mode", ("#66543c", "#493b2c", "#f4ead9", "#e4b768")
    else:
        status_text, status_colors = "Order &amp; Booking API: Offline", ("#795047", "#56352f", "#f4dfd9", "#ef987c")
    border, background, foreground, dot = status_colors
    st.markdown(
        f"<div style='border:1px solid {border};background:{background};border-radius:12px;padding:.65rem .75rem;color:{foreground};font-size:.82rem'>"
        f"<span style='color:{dot}'>&#9679;</span> &nbsp;{status_text}</div>",
        unsafe_allow_html=True,
    )
    st.caption("Gemini assistant · " + config.CHAT_MODEL)

    if st.button(":material/delete_sweep:  Clear conversation", key="clear_chat", width="stretch"):
        st.session_state.messages, st.session_state.history = [], []
        st.session_state.pending = None
        st.rerun()

# ---------------- main experience ----------------
st.markdown(
    "<div class='sg-topbar'><div class='sg-brand'><div class='sg-mark'>&#10022;</div><div><div class='sg-brand-name'>SPICE GARDEN</div><div class='sg-brand-sub'>AI Restaurant Assistant</div></div></div>"
    "<div class='sg-ready'><span class='sg-ready-dot'></span>Assistant ready</div></div>",
    unsafe_allow_html=True,
)

if st.session_state.view == "menu":
    render_full_menu()
elif not st.session_state.messages:
    st.markdown(
        "<div class='sg-hero'><div class='sg-eyebrow'>A little taste of India</div>"
        "<div class='sg-hero-title'>Namaste<br>Welcome to Spice Garden</div>"
        "<div class='sg-hero-copy'>Your AI dining assistant for menus, recommendations, orders and reservations."
        " Tell us what you're craving and we'll take it from here.</div></div>",
        unsafe_allow_html=True,
    )
    action_cols = st.columns(4, gap="medium")
    for index, (col, (icon, title, description, suggestion_key)) in enumerate(zip(action_cols, ACTION_CARDS)):
        with col:
            with st.container(key=f"hero_card_{index}"):
                st.markdown(f"<div class='sg-card-content'><div class='sg-card-icon'>{icon}</div><div class='sg-card-title'>{title}</div><div class='sg-card-copy'>{description}</div></div>", unsafe_allow_html=True)
                button_label = "Explore Menu  →" if title == "Explore the menu" else "Get started  →"
                if st.button(button_label, key=f"hero_{suggestion_key}", width="stretch"):
                    if title == "Explore the menu":
                        st.session_state.view = "menu"
                    else:
                        queue_prompt(SUGGESTIONS[suggestion_key])
                    st.rerun()
else:
    st.markdown("<div class='sg-eyebrow' style='margin-bottom:1rem'>Your conversation</div>", unsafe_allow_html=True)
    with st.container(height=560, border=False):
        with st.chat_message("assistant", avatar=":material/local_dining:"):
            st.markdown("Namaste! I'm **Spicy**, your Spice Garden dining assistant. How can I help you today?")

        for message_index, msg in enumerate(st.session_state.messages):
            avatar = ":material/local_dining:" if msg["role"] == "assistant" else None
            with st.chat_message(msg["role"], avatar=avatar):
                if msg["role"] == "assistant":
                    render_tool_steps(msg.get("tools", []))
                    tool_calls = msg.get("tools", [])
                    if any(call.get("name") == "browse_menu" for call in tool_calls):
                        render_menu_cards(tool_calls, str(message_index))
                    else:
                        st.markdown(msg["content"])
                else:
                    st.markdown(msg["content"])

typed = st.chat_input("Ask Spice Garden anything...", max_chars=4000)
prompt = typed or st.session_state.pending
st.session_state.pending = None

if prompt:
    st.session_state.view = "home"
    st.session_state.messages.append({"role": "user", "content": prompt, "tools": []})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=":material/local_dining:"):
        try:
            with st.spinner("Preparing a thoughtful answer..."):
                reply, tools, st.session_state.history = chat(get_agent(), st.session_state.history, prompt)
        except Exception as exc:
            logger.error(
                "AI chat request failed (%s). Sanitized traceback follows:\n%s",
                type(exc).__name__,
                safe_exception_traceback(exc),
            )
            reply, tools = (
                "Sorry, I'm having trouble reaching my AI service right now. Please try again in a minute.",
                [],
            )
            st.session_state.messages.pop()  # don't keep a failed turn in display history
            st.error("The assistant could not complete this request. Check the service connection and try again.", icon=":material/error:")
            st.markdown(reply)
        else:
            render_tool_steps(tools)
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply, "tools": tools})
            # Re-render the completed turn inside the scrollable transcript above the composer.
            st.rerun()
