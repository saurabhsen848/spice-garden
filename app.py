"""Spice Garden restaurant chat agent - Streamlit UI.

Run:  streamlit run app.py   (start the mock API first: uvicorn mock_api.server:app --port 8000)
"""

import json

import requests
import streamlit as st

from agent import config
from agent.agent import build_agent, chat

st.set_page_config(page_title="Spice Garden assistant", page_icon=":material/restaurant:")

# Friendly labels for the tool-call timeline shown under each reply.
TOOL_LABELS = {
    "search_menu": ":material/search: Searched the menu (RAG)",
    "browse_menu": ":material/menu_book: Opened the menu",
    "recommend_dishes": ":material/thumb_up: Filtered dishes for recommendations",
    "search_restaurant_info": ":material/info: Searched policies & FAQs (RAG)",
    "check_order_status": ":material/local_shipping: Called order API",
    "check_table_availability": ":material/event_available: Called availability API",
    "make_reservation": ":material/event_seat: Called reservation API",
}

SUGGESTIONS = {
    ":material/menu_book: Show me the menu": "Show me the full menu",
    ":material/thumb_up: Recommend a veg dish": "Can you recommend a vegetarian dish that is not too spicy?",
    ":material/local_shipping: Track my order": "I want to track my order ORD1002",
    ":material/event_seat: Book a table": "I'd like to book a table",
    ":material/schedule: Opening hours": "What are your opening hours and where are you located?",
}


@st.cache_resource(ttl=3600)  # rebuilt hourly so "today's date" in the system prompt stays correct
def get_agent():
    return build_agent()


def api_is_up() -> bool:
    try:
        return requests.get(config.API_BASE_URL, timeout=2).ok
    except requests.RequestException:
        return False


def render_tool_steps(tools: list[dict]) -> None:
    """Collapsed timeline of the tools the agent called for one reply."""
    if not tools:
        return
    noun = "tool" if len(tools) == 1 else "tools"
    with st.expander(f"Used {len(tools)} {noun}", type="compact"):
        for t in tools:
            with st.status(TOOL_LABELS.get(t["name"], t["name"]), type="step", state="complete"):
                st.code(f"{t['name']}({json.dumps(t['args'], ensure_ascii=False)})", language="python")


# ---------------- session state ----------------
if "messages" not in st.session_state:
    st.session_state.messages = []      # for display: {"role", "content", "tools"}
    st.session_state.history = []       # LangChain messages = the agent's conversation memory
    st.session_state.pending = None     # prompt queued by a sidebar button or suggestion

# ---------------- sidebar ----------------
with st.sidebar:
    st.header(":material/restaurant: Spice Garden")
    st.caption("Multi-cuisine Indian restaurant · MG Road, Bengaluru")

    with st.container(border=True):
        st.markdown(
            "**:material/schedule: Hours**  \n"
            "Mon–Fri: 12:00–3:30 PM, 7:00–11:00 PM  \n"
            "Sat–Sun: 12:00 PM–11:30 PM  \n\n"
            "**:material/call: Phone**  \n+91 8969700172"
        )

    st.subheader("Quick actions")
    for label, prompt in SUGGESTIONS.items():
        if st.button(label, width="stretch"):
            st.session_state.pending = prompt

    st.divider()
    if api_is_up():
        st.badge("Order & booking API online", icon=":material/check_circle:", color="green")
    else:
        st.badge("Order & booking API offline", icon=":material/error:", color="red")
    st.caption(f"Model: `{config.CHAT_MODEL}`")

    if st.button(":material/delete: Clear chat", width="stretch"):
        st.session_state.messages, st.session_state.history = [], []
        st.rerun()

# ---------------- main chat ----------------
st.title("Spice Garden assistant")
st.caption("Ask about our menu, get recommendations, track an order or reserve a table.")

with st.chat_message("assistant", avatar=":material/restaurant:"):
    st.markdown("Namaste! I'm **Spicy**, Spice Garden's virtual assistant. How can I help you today?")

for msg in st.session_state.messages:
    avatar = ":material/restaurant:" if msg["role"] == "assistant" else None
    with st.chat_message(msg["role"], avatar=avatar):
        if msg["role"] == "assistant":
            render_tool_steps(msg["tools"])
        st.markdown(msg["content"])

if not st.session_state.messages:
    choice = st.pills("Try asking", list(SUGGESTIONS), label_visibility="collapsed")
    if choice:
        st.session_state.pending = SUGGESTIONS[choice]

typed = st.chat_input("Type your message…", submit_mode="disable")
prompt = typed or st.session_state.pending
st.session_state.pending = None

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt, "tools": []})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar=":material/restaurant:"):
        try:
            with st.spinner("Thinking…"):
                reply, tools, st.session_state.history = chat(get_agent(), st.session_state.history, prompt)
        except Exception as exc:  # show a friendly message instead of a stack trace
            reply, tools = ("Sorry, I'm having trouble reaching my AI service right now. "
                            "Please try again in a minute."), []
            st.session_state.messages.pop()  # don't keep the failed turn in history
            st.error(f"{type(exc).__name__}: {str(exc)[:300]}", icon=":material/error:")
            st.markdown(reply)
        else:
            render_tool_steps(tools)
            st.markdown(reply)
            st.session_state.messages.append({"role": "assistant", "content": reply, "tools": tools})
