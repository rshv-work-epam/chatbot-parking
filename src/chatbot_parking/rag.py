"""Retrieval-augmented generation helpers."""

from dataclasses import dataclass
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.embeddings import FakeEmbeddings

from chatbot_parking.static_docs import STATIC_DOCUMENTS


@dataclass
class RetrievalResult:
    documents: List[Document]


def build_vector_store(embeddings: Embeddings | None = None) -> FAISS:
    docs = [Document(page_content=doc["text"], metadata={"id": doc["id"]}) for doc in STATIC_DOCUMENTS]
    embedder = embeddings or FakeEmbeddings(size=256)
    return FAISS.from_documents(docs, embedder)


def retrieve(query: str, store: FAISS, k: int = 3) -> RetrievalResult:
    docs = store.similarity_search(query, k=k)
    return RetrievalResult(documents=docs)
