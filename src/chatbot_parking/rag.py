"""Retrieval-augmented generation helpers."""

from dataclasses import dataclass
import os
from urllib.parse import urlparse
from typing import List

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.embeddings import FakeEmbeddings
from langchain_core.language_models.llms import LLM
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from chatbot_parking.config import get_settings
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


def _build_embeddings() -> Embeddings:
    settings = get_settings()
    if settings.embeddings_provider == "fake":
        return FakeEmbeddings(size=256)
    if settings.embeddings_provider == "openai":
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(api_key=settings.openai_api_key)
    if settings.embeddings_provider == "hf":
        from langchain_community.embeddings import HuggingFaceEmbeddings

        return HuggingFaceEmbeddings(model_name=settings.embeddings_model)
    raise ValueError(f"Unsupported embeddings provider: {settings.embeddings_provider}")


def build_vector_store(embeddings: Embeddings | None = None, insert_documents: bool = True):
    settings = get_settings()
    docs = _prepare_documents()
    embedder = embeddings or _build_embeddings()

    if settings.vector_backend == "weaviate":
        import weaviate
        from langchain_weaviate import WeaviateVectorStore

        parsed_url = urlparse(settings.weaviate_url)
        http_host = parsed_url.hostname or settings.weaviate_url
        http_port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)
        http_secure = parsed_url.scheme == "https"
        grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
        client = weaviate.connect_to_custom(
            http_host=http_host,
            http_port=http_port,
            http_secure=http_secure,
            grpc_host=http_host,
            grpc_port=grpc_port,
            grpc_secure=http_secure,
        )
        if insert_documents:
            return WeaviateVectorStore.from_documents(
                docs,
                embedder,
                client=client,
                index_name=settings.weaviate_index,
                text_key="text",
            )
        return WeaviateVectorStore(
            client=client,
            index_name=settings.weaviate_index,
            text_key="text",
            embedding=embedder,
        )

    return FAISS.from_documents(docs, embedder)


def retrieve(query: str, store, k: int = 3) -> RetrievalResult:
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


def _build_llm() -> LLM:
    settings = get_settings()
    if settings.llm_provider == "echo":
        return EchoLLM()
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=settings.llm_model, api_key=settings.openai_api_key)
    if settings.llm_provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI

        if not settings.azure_openai_endpoint or not settings.azure_openai_deployment:
            raise ValueError("Azure OpenAI endpoint and deployment must be set.")
        return AzureChatOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            azure_deployment=settings.azure_openai_deployment,
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")


def generate_answer(question: str, context: str, dynamic_info: str) -> str:
    prompt = PromptTemplate.from_template(
        "Context:\n{context}\n\nDynamic info:\n{dynamic}\n\nQuestion: {question}\nAnswer:"
    )
    chain = prompt | _build_llm() | StrOutputParser()
    return chain.invoke({"question": question, "context": context, "dynamic": dynamic_info})
