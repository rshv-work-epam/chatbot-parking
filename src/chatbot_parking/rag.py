"""Retrieval-augmented generation helpers."""

from dataclasses import dataclass
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.embeddings import FakeEmbeddings
from langchain_core.language_models.llms import LLM
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

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


class EchoLLM(LLM):
    """Minimal LLM implementation that echoes a summarized response for demos."""

    def _call(self, prompt: str, stop: list[str] | None = None) -> str:
        response = prompt.split("Answer:")[-1].strip()
        return response or "I could not generate an answer."

    @property
    def _llm_type(self) -> str:
        return "echo"


def generate_answer(question: str, context: str, dynamic_info: str) -> str:
    prompt = PromptTemplate.from_template(
        "Context:\n{context}\n\nDynamic info:\n{dynamic}\n\nQuestion: {question}\nAnswer:"
    )
    chain = prompt | EchoLLM() | StrOutputParser()
    return chain.invoke({"question": question, "context": context, "dynamic": dynamic_info})
