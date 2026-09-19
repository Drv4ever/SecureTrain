"""Build the local Chroma index from data/phishing_indicators markdown files."""

from app.rag import get_retriever


if __name__ == "__main__":
    retriever = get_retriever()
    count = retriever.collection.count() if getattr(retriever, "collection", None) else len(getattr(retriever, "_fallback_docs", []))
    print(f"RAG knowledge base ready: {count} indicator documents indexed.")
