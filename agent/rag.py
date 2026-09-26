"""Retrieval-Augmented Generation: builds and queries the FAISS knowledge base.

Two kinds of documents are indexed:
  * kind="menu" - one document per dish, generated from data/menu.json
  * kind="info" - one document per section of data/policies.md and data/faq.md
"""

import json
from functools import lru_cache

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter

from agent import config

SPICE_LABELS = {0: "not spicy", 1: "mild", 2: "medium", 3: "hot"}


def load_menu() -> list[dict]:
    return json.loads(config.MENU_FILE.read_text(encoding="utf-8"))


def dish_to_text(dish: dict) -> str:
    """Readable one-paragraph description of a dish (used for embedding and display)."""
    allergens = ", ".join(dish["allergens"]) if dish["allergens"] else "none listed"
    return (
        f"{dish['name']} ({dish['category']}) - Rs.{dish['price']}. "
        f"{'Vegetarian' if dish['veg'] else 'Non-vegetarian'}. "
        f"Spice level: {dish['spice']}/3 ({SPICE_LABELS[dish['spice']]}). "
        f"Allergens: {allergens}. {dish['description']}"
    )


def _menu_documents() -> list[Document]:
    return [
        Document(page_content=dish_to_text(d),
                 metadata={"kind": "menu", "source": "menu.json", "category": d["category"], "name": d["name"]})
        for d in load_menu()
    ]


def _info_documents() -> list[Document]:
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("#", "title"), ("##", "section")])
    docs = []
    for path in config.INFO_FILES:
        for chunk in splitter.split_text(path.read_text(encoding="utf-8")):
            section = chunk.metadata.get("section")
            if not section:  # skip the bare document title
                continue
            # Prefix the heading so the chunk is self-explanatory when retrieved.
            docs.append(Document(page_content=f"{section}\n{chunk.page_content}",
                                 metadata={"kind": "info", "source": path.name, "section": section}))
    return docs


def _embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(model=config.EMBED_MODEL, google_api_key=config.GOOGLE_API_KEY)


def build_index() -> int:
    """Embed all documents and save the FAISS index to disk. Returns the document count."""
    docs = _menu_documents() + _info_documents()
    FAISS.from_documents(docs, _embeddings()).save_local(str(config.VECTORSTORE_DIR))
    get_vectorstore.cache_clear()
    return len(docs)


@lru_cache(maxsize=1)
def get_vectorstore() -> FAISS:
    if not (config.VECTORSTORE_DIR / "index.faiss").exists():
        build_index()
    # The index is created locally by build_index(), so deserialising it is safe.
    return FAISS.load_local(str(config.VECTORSTORE_DIR), _embeddings(), allow_dangerous_deserialization=True)


def retrieve(query: str, kind: str, k: int = 4) -> list[Document]:
    """Top-k most similar documents of the given kind ("menu" or "info")."""
    return get_vectorstore().similarity_search(query, k=k, filter={"kind": kind}, fetch_k=40)
