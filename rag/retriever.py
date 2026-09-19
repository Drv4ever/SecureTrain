"""RAG (Retrieval-Augmented Generation) indicator retriever.

Embeds and retrieves documented phishing indicators from data/phishing_indicators/
using SentenceTransformer ('all-MiniLM-L6-v2') and ChromaDB.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import re

BASE_DIR = Path(__file__).resolve().parent.parent
DOCS_PATH = BASE_DIR / "rag" / "indicators"
CHROMA_PATH = BASE_DIR / "data" / "chroma_store"


def parse_frontmatter(content: str) -> tuple[Dict[str, str], str]:
    """Extract YAML-style metadata frontmatter and body from markdown."""
    metadata: Dict[str, str] = {}
    body = content.strip()
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            raw_meta, body = parts[1].strip(), parts[2].strip()
            for line in raw_meta.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    metadata[k.strip()] = v.strip()
    return metadata, body


class IndicatorRetriever:
    """Retrieves grounded phishing indicator documents filtered by attack tactic."""

    def __init__(self, docs_path: Path = DOCS_PATH, chroma_path: Path = CHROMA_PATH):
        self.docs_path = Path(docs_path)
        self.chroma_path = Path(chroma_path)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self._initialized = False
        self._fallback_docs: List[Dict[str, Any]] = []

        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            self.encoder = SentenceTransformer("all-MiniLM-L6-v2")
            self.client = chromadb.PersistentClient(path=str(self.chroma_path))
            self.collection = self.client.get_or_create_collection("phishing_indicators")
            self._ensure_indexed()
            self._initialized = True
        except Exception as exc:
            print(f"[RAG Warning] Vector store init failed ({exc}); falling back to in-memory markdown retriever.")
            self._load_fallback_docs()

    def _load_fallback_docs(self):
        """Read all documents into in-memory list for zero-dependency fallback."""
        self._fallback_docs = []
        if not self.docs_path.exists():
            return
        for md_file in sorted(self.docs_path.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
                meta, body = parse_frontmatter(content)
                self._fallback_docs.append({
                    "id": meta.get("id", md_file.stem),
                    "tactic": meta.get("tactic", "general"),
                    "title": meta.get("title", md_file.stem.replace("_", " ").title()),
                    "source": meta.get("source", "Cybersecurity Reference Guidelines"),
                    "technique": meta.get("technique", "Phishing Technique"),
                    "text": body,
                    "snippet": body[:220] + ("..." if len(body) > 220 else ""),
                })
            except Exception as e:
                print(f"[RAG Warning] Could not read {md_file}: {e}")

    def _ensure_indexed(self):
        """Load and embed markdown indicators on first run if collection is empty."""
        count = self.collection.count()
        if count > 0:
            return

        if not self.docs_path.exists():
            print(f"[RAG Warning] Indicator docs directory {self.docs_path} not found.")
            return

        ids, docs, metas = [], [], []
        for md_file in sorted(self.docs_path.glob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(content)
            doc_id = meta.get("id", md_file.stem)
            tactic = meta.get("tactic", "general")
            title = meta.get("title", md_file.stem)
            source = meta.get("source", "Standard Security Reference")
            technique = meta.get("technique", "Phishing Pattern")

            ids.append(doc_id)
            docs.append(f"{title}\n{technique}\n{body}")
            metas.append({
                "id": doc_id,
                "tactic": tactic,
                "title": title,
                "source": source,
                "technique": technique,
                "body": body,
            })

        if docs:
            embeddings = self.encoder.encode(docs).tolist()
            self.collection.add(
                ids=ids,
                documents=docs,
                embeddings=embeddings,
                metadatas=metas,
            )
            print(f"[RAG] Successfully indexed {len(docs)} phishing indicator documents into ChromaDB.")

    def retrieve(self, tactic: str, query: Optional[str] = None, k: int = 3) -> List[Dict[str, Any]]:
        """Retrieve top-k reference indicator documents for a given tactic."""
        tactic = tactic.lower().strip()
        if self._initialized:
            try:
                search_query = query if query and query.strip() else f"phishing indicators for {tactic} attacks and exploitation patterns"
                query_embedding = self.encoder.encode([search_query]).tolist()
                results = self.collection.query(
                    query_embeddings=query_embedding,
                    n_results=k,
                    where={"tactic": tactic},
                )
                retrieved = []
                if results and "metadatas" in results and results["metadatas"]:
                    for meta in results["metadatas"][0]:
                        body = meta.get("body", "")
                        retrieved.append({
                            "id": meta.get("id"),
                            "tactic": meta.get("tactic"),
                            "title": meta.get("title"),
                            "source": meta.get("source"),
                            "technique": meta.get("technique"),
                            "text": body,
                            "snippet": body[:220] + ("..." if len(body) > 220 else ""),
                        })
                if retrieved:
                    return retrieved
            except Exception as exc:
                print(f"[RAG Warning] Chroma query failed ({exc}); using fallback.")

        # Fallback keyword/tactic search
        if not self._fallback_docs:
            self._load_fallback_docs()
        matched = [d for d in self._fallback_docs if d["tactic"] == tactic]
        return matched[:k] if matched else self._fallback_docs[:k]


_retriever_instance: Optional[IndicatorRetriever] = None


def get_retriever() -> IndicatorRetriever:
    """Return the cached singleton IndicatorRetriever instance."""
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = IndicatorRetriever()
    return _retriever_instance


