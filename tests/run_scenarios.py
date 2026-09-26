"""End-to-end demo scenarios against the real agent (needs the mock API running and a Gemini key).

Run:  python -m tests.run_scenarios
Each scenario is a list of user turns in one conversation; the tools called are printed for each turn.
"""

import sys

from agent.agent import build_agent, chat

SCENARIOS = {
    "1. Browse menu": ["What starters do you have?"],
    "2. Recommendation": ["Suggest something vegetarian, not too spicy, under 300 rupees"],
    "3. Allergen question": ["Does the paneer butter masala contain nuts?"],
    "4. FAQ - timings & location": ["What are your timings on Sunday and where are you located?"],
    "5. Order status": ["Where is my order ORD1003?"],
    "6. Unknown order": ["Track order ORD9999"],
    "7. Reservation (multi-turn)": [
        "I want to book a table for 4 tomorrow at 8pm",
        "Name is Rohan Gupta, phone 9876543210",
        "Yes, please confirm",
    ],
    "8. Policy violation": ["Book a table for 50 people tomorrow at 3am, name Test, phone 9999999999"],
    "9. Memory / follow-up": ["What desserts do you have?", "Which of those are vegan?"],
    "10. Off-topic": ["Can you write my college homework on thermodynamics?"],
}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    only = sys.argv[1:]  # optionally pass scenario numbers, e.g. "5 7"
    for title, turns in SCENARIOS.items():
        if only and title.split(".")[0] not in only:
            continue
        print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")
        agent, history = build_agent(), []
        for user in turns:
            reply, calls, history = chat(agent, history, user)
            print(f"\nYou:   {user}")
            for c in calls:
                print(f"       [tool] {c['name']}({c['args']})")
            print(f"Spicy: {reply}")
