"""One-time script: builds the FAISS vector store from the files in data/.

Re-run it whenever the menu, policies or FAQ change.
"""

from agent.rag import build_index, retrieve

if __name__ == "__main__":
    count = build_index()
    print(f"Indexed {count} documents into the vector store.")

    print("\nSanity check:")
    for query, kind in [("dessert without dairy", "menu"), ("what time do you open on Sunday", "info")]:
        top = retrieve(query, kind, k=1)[0]
        print(f"  '{query}' -> {top.page_content[:90]}...")
