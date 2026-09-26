# Restaurant Chat Agent: Project Plan

## 1. Goal

Build an AI chat agent for one fictional restaurant. Customers should be able to:

| # | Feature (from abstract) | How it is implemented |
|---|---|---|
| 1 | Browse menu items | RAG over the menu document |
| 2 | Personalized dish recommendations | RAG + tool with filters (veg/non-veg, spice level, budget, allergens) |
| 3 | Check order status via a **mock API** | Tool → HTTP call to a local FastAPI mock server |
| 4 | Make table reservations | Tools → mock API (check availability, then book) |
| 5 | FAQs: timings, location, policies | RAG over policy/FAQ documents |
| 6 | Natural conversation | LangChain tool-calling agent + chat memory |
| 7 | Chat interface | Streamlit web UI |

Every item in the abstract maps to a row above. Nothing extra is added.

## 2. Tech Stack (kept minimal)

| Layer | Choice | Why |
|---|---|---|
| Language | Python **3.13** (in a venv) | Stable wheels for FAISS/LangChain; already installed on this machine |
| Agent framework | LangChain (tool-calling agent) | Required by the abstract |
| LLM | **Google Gemini** (`gemini-flash-latest`) via `langchain-google-genai` *(see decision 1)* | Free tier, supports tool calling |
| Embeddings | Gemini embeddings (`gemini-embedding-001`) | Same API key, no heavy local model download |
| Vector store | FAISS (`faiss-cpu`), saved to disk | Simple, no server needed |
| Mock API | FastAPI + Uvicorn, data in JSON files | Shows real HTTP API integration |
| UI | Streamlit chat (`st.chat_message`) | Fastest way to get a clean chat UI |
| Config | `.env` file (`python-dotenv`) | Keeps the API key out of code |

## 3. Architecture

```
 ┌──────────────┐     user msg      ┌──────────────────────────────┐
 │  Streamlit   │ ────────────────► │   LangChain Agent (LLM)      │
 │  Chat UI     │ ◄──────────────── │   + system prompt + memory   │
 └──────────────┘     reply         └──────────────┬───────────────┘
                                                   │ decides which tool to call
             ┌──────────────────────┬──────────────┼───────────────────────┐
             ▼                      ▼              ▼                       ▼
     search_menu /          search_policies   check_order_status    check_availability /
     recommend_dishes         (RAG)              (HTTP GET)          make_reservation (HTTP POST)
             │                      │              │                       │
             ▼                      ▼              └──────────┬────────────┘
     ┌─────────────────────────────────────┐                  ▼
     │ FAISS vector store                  │        ┌───────────────────────┐
     │ (menu.md + policies.md + faq.md)    │        │ FastAPI mock server   │
     └─────────────────────────────────────┘        │ orders.json,          │
                                                    │ reservations.json     │
                                                    └───────────────────────┘
```

**Flow:** the user asks something. The agent reads the question and chat history, picks a tool (or none, for small talk), gets the tool result, and writes a grounded answer. The system prompt tells the agent to **only** state menu, price, and policy facts that come from retrieved data. That keeps it from inventing dishes or prices.

## 4. Project Structure

```
gen-ai-project/
├── data/
│   ├── menu.json            # 29 dishes: single source for RAG docs + recommendation filters
│   ├── policies.md          # hours, location, reservation/cancellation, delivery, payment, allergy policy
│   └── faq.md               # common Q&A (parking, kids, parties, Wi-Fi, etc.)
├── mock_api/
│   ├── server.py            # FastAPI app
│   ├── orders.json          # ~10 sample orders with various statuses
│   └── reservations.json    # bookings (written to by the API)
├── agent/
│   ├── config.py            # loads .env, model names, API base URL
│   ├── rag.py               # load docs → chunk → embed → FAISS build/load → retriever
│   ├── tools.py             # all @tool functions
│   ├── prompts.py           # system prompt
│   └── agent.py             # builds the agent (LLM + tools + memory)
├── app.py                   # Streamlit chat UI
├── build_index.py           # one-time: builds the FAISS index from data/
├── tests/
│   ├── test_mock_api.py     # pytest for API endpoints
│   └── run_scenarios.py     # 10 end-to-end demo conversations against the real agent
├── .env.example
├── requirements.txt
└── README.md                # setup, run steps, screenshots, architecture
```

## 5. Component Details

### 5.1 Knowledge base (RAG data)
- A fictional restaurant, e.g. **"Spice Garden"**, a multi-cuisine Indian restaurant *(decision 3)*.
- `menu.json` has 29 dishes across Starters / Mains / Breads / Desserts / Beverages. Each dish lists price (₹), veg/non-veg, spice level (0–3), allergens, and a one-line description. One RAG document is generated per dish, so the RAG search and the filters never disagree.
- `policies.md` + `faq.md` cover opening hours, address and landmark, contact, reservation rules (max party size, hold time), cancellation, delivery radius, payment modes, allergy disclaimer, and dress code.
- **Chunking:** split by markdown headings (one dish or one policy per chunk) so retrieval stays precise. Each chunk keeps metadata `{source, category}`.

### 5.2 Tools (LangChain `@tool`)
| Tool | Input | What it does |
|---|---|---|
| `search_menu(query)` | free text | Top-k retrieval from menu chunks |
| `browse_menu(category)` | optional category | Lists the full menu or one category (added: top-k RAG can't list everything) |
| `recommend_dishes(preferences)` | veg?, max_spice, max_price, exclude_allergens, category | Filters `menu.json`, then the LLM explains why each pick fits |
| `search_restaurant_info(query)` | free text | Top-k retrieval from policies + FAQ |
| `check_order_status(order_id)` | e.g. `ORD1003` | `GET /orders/{id}` → status, items, ETA |
| `check_table_availability(date, time, party_size)` | | `GET /reservations/availability` |
| `make_reservation(name, phone, date, time, party_size)` | | `POST /reservations` → confirmation ID |

The agent asks follow-up questions when required fields are missing, e.g. "For how many people?" before booking.

### 5.3 Mock API (FastAPI)
- `GET  /orders/{order_id}`: returns an order or 404
- `GET  /reservations/availability?date=&time=&party_size=`: simple rule: 10 tables per slot, closed outside opening hours, rejects past dates
- `POST /reservations`: validates input, saves to `reservations.json`, returns `RES-XXXX`
- `GET  /reservations/{id}`: look up a booking (useful for the demo)
- Auto-generated Swagger docs at `/docs`, which are good for showing in the report and viva.

### 5.4 Agent
- LangChain tool-calling agent with the 6 tools above.
- System prompt: restaurant persona, polite and concise, use tools for facts, never make up prices or dishes, confirm details before booking, and politely decline off-topic requests.
- Memory: conversation history kept in Streamlit `session_state` and passed to the agent each turn.

### 5.5 UI (Streamlit)
- Chat window with history, a welcome message, and a sidebar containing restaurant info, **quick-action buttons** ("Show menu", "Recommend something veg", "Track my order", "Book a table"), and a "Clear chat" button.
- Optional expander "🔧 Tools used" under each reply, which shows which tool was called. Handy for demonstrating tool calling to the evaluator.

## 6. Build Phases

| Phase | Work | Done when |
|---|---|---|
| 1. Setup | venv (3.11), `requirements.txt`, `.env`, folder skeleton | `pip install` succeeds |
| 2. Data | Write menu, policies, FAQ, sample orders | Files reviewed for consistency |
| 3. Mock API | FastAPI server + pytest tests | `/docs` works, tests pass |
| 4. RAG | `rag.py` + `build_index.py` | Test queries return the right chunks |
| 5. Tools + Agent | `tools.py`, `prompts.py`, `agent.py`; CLI test loop | Agent answers all sample queries correctly in the terminal |
| 6. UI | `app.py` Streamlit chat | Full demo works in the browser |
| 7. Test & polish | Run `sample_queries.md`, fix prompt issues, write README | All scenarios pass, README complete |

**Run commands (final):**
```
uvicorn mock_api.server:app --port 8000     # terminal 1
python build_index.py                        # once
streamlit run app.py                         # terminal 2
```

## 7. Test Scenarios (demo script)
1. "What's on the menu for starters?" → `search_menu`
2. "Suggest something vegetarian, not too spicy, under ₹300" → `recommend_dishes`
3. "Does the paneer tikka contain nuts?" → `search_menu` (allergen)
4. "What are your timings on Sunday?" / "Where are you located?" → `search_restaurant_info`
5. "Where is my order ORD1003?" → `check_order_status`
6. "Track order ORD9999" → graceful "not found"
7. "Book a table for 4 tomorrow at 8pm" → asks for name/phone → availability → booking → confirmation ID
8. Booking at 3 AM or for 50 people → politely rejected per policy
9. Multi-turn: "What desserts do you have?" → "Is the second one vegan?" (memory)
10. Off-topic: "Write my homework" → polite refusal

## 8. Out of Scope (deliberately excluded)
User login/auth, real payment, a real database, online ordering/cart, Docker/cloud deployment, voice, multi-language, admin dashboard, fine-tuning. None of these are in the abstract, and they would add risk without adding marks.

## 9. Decisions Needed From You
1. **LLM provider.** The recommendation is **Google Gemini (free API key from aistudio.google.com)**. Alternatives are OpenAI, Anthropic Claude, or Groq (all paid or rate-limited, but the code swaps with one line). Do you already have a key for any of these?
2. **UI.** Streamlit is recommended. Is a plain terminal chat acceptable instead? (Streamlit is better for demos.)
3. **Restaurant theme.** A fictional Indian multi-cuisine restaurant "Spice Garden" with prices in ₹. Is that fine, or do you want a different name or cuisine?
4. **Anything your college requires**, such as a specific report format, a diagram, or a Jupyter notebook submission?
