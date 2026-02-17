from collections import Counter

from langchain_text_splitters import RecursiveCharacterTextSplitter

from chatbot_parking.rag import _build_splitter, _prepare_documents


def test_chunking_adds_chunk_and_source_metadata():
    docs = _prepare_documents(chunk_size=40, chunk_overlap=10, splitter_type="token")

    assert docs
    for doc in docs:
        assert "source_id" in doc.metadata
        assert "chunk_id" in doc.metadata
        assert "chunk_index" in doc.metadata


def test_small_chunk_size_splits_at_least_one_source_into_multiple_chunks():
    docs = _prepare_documents(chunk_size=20, chunk_overlap=5, splitter_type="token")

    counts = Counter(doc.metadata["source_id"] for doc in docs)
    assert any(count > 1 for count in counts.values())


def test_default_splitter_is_offline_safe_recursive():
    splitter = _build_splitter()
    assert isinstance(splitter, RecursiveCharacterTextSplitter)
