"""Retrieval-augmented generation helpers."""

from dataclasses import dataclass
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.embeddings import FakeEmbeddings

from chatbot_parking.static_docs import STATIC_DOCUMENTS
from chatbot_parking.guardrails import SensitiveDataDetector


@dataclass
class RetrievalResult:
    documents: List[Document]


def build_vector_store(
    embeddings: Embeddings | None = None,
    detector: SensitiveDataDetector | None = None,
) -> FAISS:
    active_detector = detector or SensitiveDataDetector()
    docs: list[Document] = []
    for doc in STATIC_DOCUMENTS:
        if doc.get("sensitivity") == "private":
            continue
        if active_detector.contains_sensitive_data(doc["text"]):
            continue
        docs.append(
            Document(
                page_content=doc["text"],
                metadata={"id": doc["id"], "sensitivity": doc.get("sensitivity", "public")},
            )
        )
    embedder = embeddings or FakeEmbeddings(size=256)
    return FAISS.from_documents(docs, embedder)


def retrieve(query: str, store: FAISS, k: int = 3) -> RetrievalResult:
    docs = store.similarity_search(query, k=k)
    public_docs = [doc for doc in docs if doc.metadata.get("sensitivity") != "private"]
    return RetrievalResult(documents=public_docs)
