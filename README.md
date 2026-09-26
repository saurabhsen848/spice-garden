# Spice Garden – AI Restaurant Chat Agent

An AI-powered customer-support chat agent for a (fictional) restaurant, **Spice Garden**, built with
**Generative AI (Google Gemini)**, **LangChain**, **Retrieval-Augmented Generation (RAG)** and **tool calling**.

Customers can:

- browse the menu and ask about dishes (price, spice level, allergens)
- get personalised dish recommendations (veg, spice, budget, allergies)
- check the status of an order through a mock order-tracking API
- check table availability and make reservations through a mock reservation API
- ask FAQs such as opening hours, location, parking, payment and cancellation policy

## Architecture

```
 Streamlit chat UI  ──►  LangChain tool-calling agent (Gemini) + conversation memory
                                 │ picks a tool
     ┌───────────────┬───────────┼────────────────────┬─────────────────────────┐
     ▼               ▼           ▼                    ▼                         ▼
 search_menu    browse_menu  recommend_dishes  search_restaurant_info   check_order_status
   (RAG)        (menu.json)   (menu.json         (RAG)                  check_table_availability
     │                         filters)            │                    make_reservation
     ▼                                             ▼                         │ HTTP
  FAISS vector store  ◄── Gemini embeddings ── menu.json, policies.md, faq.md │
                                                                             ▼
                                                     FastAPI mock API (orders.json, reservations.json)
```

| Concept | Where it is implemented |
|---|---|
| Generative AI (LLM) | `agent/agent.py` – Gemini via `langchain-google-genai` |
| LangChain agent | `agent/agent.py` – `create_agent` with 7 tools and a system prompt |
| RAG | `agent/rag.py` – documents → Gemini embeddings → FAISS → similarity search |
| Tool calling | `agent/tools.py` – `@tool` functions the LLM chooses between |
| API integration | `mock_api/server.py` – FastAPI service called over HTTP by the tools |
| Conversational memory | Full message history passed to the agent on every turn |
| Grounding / hallucination control | `agent/prompts.py` – agent must answer facts only from tools |

## Project structure

```
data/            menu.json, policies.md, faq.md        – the knowledge base
mock_api/        server.py, orders.json, reservations.json – mock restaurant backend
agent/           config.py, rag.py, tools.py, prompts.py, agent.py
app.py           Streamlit chat UI
build_index.py   builds the FAISS vector store
tests/           test_mock_api.py (pytest), run_scenarios.py (end-to-end demo)
```

## Setup

Requires Python 3.11–3.13 and a Gemini API key from <https://aistudio.google.com/apikey>.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env            # then put your key in .env
python build_index.py             # one time: builds the vector store
```

## Run

Open two terminals (with the venv activated):

```bash
# Terminal 1 – mock order/reservation API  (API docs at http://127.0.0.1:8000/docs)
uvicorn mock_api.server:app --port 8000

# Terminal 2 – chat UI  (opens http://localhost:8501)
streamlit run app.py
```

There is also a terminal chat: `python -m agent.agent`.

## Testing

```bash
pytest tests                       # mock API unit tests (12 tests)
python -m tests.run_scenarios      # 10 end-to-end conversations against the real agent
python -m tests.run_scenarios 5 7  # run selected scenarios only
```

Sample order IDs for the demo: `ORD1001` to `ORD1008` (delivered, out for delivery, preparing, ready for pickup,
received, cancelled, delayed).

## Notes

- **Free-tier limits:** Gemini's free tier allows only a few requests per minute, and each chat turn uses 2–3.
  The agent waits and retries automatically, so a reply can occasionally take 20–60 seconds. It retries only
  the model call, never the tool, so a booking is never made twice.
- To change the model, edit `CHAT_MODEL` in `.env` (e.g. `gemini-flash-latest`).
- If you edit anything in `data/`, re-run `python build_index.py`.
