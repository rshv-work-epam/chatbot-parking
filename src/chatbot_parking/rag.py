"""Retrieval-augmented generation helpers."""

from dataclasses import dataclass
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.embeddings import FakeEmbeddings

from chatbot_parking.guardrails import contains_sensitive_data, redact_sensitive
from chatbot_parking.static_docs import STATIC_DOCUMENTS


@dataclass
class RetrievalResult:
    documents: List[Document]


def _prepare_documents() -> list[Document]:
    documents: list[Document] = []
    for doc in STATIC_DOCUMENTS:
        redacted = redact_sensitive(doc["text"])
        sensitivity = "private" if contains_sensitive_data(doc["text"]) else "public"
        documents.append(
            Document(
                page_content=redacted,
                metadata={"id": doc["id"], "sensitivity": sensitivity},
            )
        )
    return documents


def build_vector_store(embeddings: Embeddings | None = None) -> FAISS:
    docs = _prepare_documents()
    embedder = embeddings or FakeEmbeddings(size=256)
    return FAISS.from_documents(docs, embedder)


def retrieve(query: str, store: FAISS, k: int = 3) -> RetrievalResult:
    docs = store.similarity_search(query, k=k)
    public_docs = [doc for doc in docs if doc.metadata.get("sensitivity") != "private"]
    return RetrievalResult(documents=public_docs)
