import uuid

import pytest

from pipeline.chunk import CHUNK_SIZE, MIN_CHUNK_CHARS, chunk_document
from pipeline.clean import clean_document
from pipeline.embed import DIMENSION, check_vector
from pipeline.files import RAW_DIR, read_json
from pipeline.models import CleanDoc
from pipeline.store import point_id


def make_doc(text: str) -> CleanDoc:
    return CleanDoc(
        id="d", title="Doc", source="s", url="", license="", text=text, doc_hash="h", removed={},
    )


def test_chunks_keep_section_titles_and_respect_sizes():
    sentence = "Pumped storage moves water uphill when power is cheap and back down when it is needed. "
    text = sentence * 3 + "\n\n## Operation\n" + sentence * 30 + "\n\n### Efficiency\n" + sentence * 2
    chunks, dropped = chunk_document(make_doc(text))
    sections = [c.section for c in chunks]
    assert sections[0] == "Introduction"
    assert "Operation" in sections
    assert sections[-1] == "Operation > Efficiency"
    assert all(MIN_CHUNK_CHARS <= len(c.text) <= CHUNK_SIZE for c in chunks)
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    assert sum(dropped.values()) == 0


def test_short_chunks_are_dropped_and_counted():
    chunks, dropped = chunk_document(make_doc("## Tiny\nToo short."))
    assert chunks == []
    assert dropped["short"] == 1


def test_chunking_a_real_article_is_deterministic():
    doc = clean_document(read_json(RAW_DIR / "pumped-storage-hydroelectricity.json"))
    first, _ = chunk_document(doc)
    second, _ = chunk_document(doc)
    assert first == second
    assert len(first) > 5


def test_point_ids_are_deterministic_uuids():
    assert point_id("abc", 0) == point_id("abc", 0)
    assert point_id("abc", 0) != point_id("abc", 1)
    assert point_id("abc", 0) != point_id("abd", 0)
    uuid.UUID(point_id("abc", 0))


@pytest.mark.parametrize("vector", [[0.1] * 10, [float("nan")] + [0.1] * (DIMENSION - 1), [0.0] * DIMENSION])
def test_check_vector_rejects_bad_embeddings(vector):
    with pytest.raises(ValueError):
        check_vector(vector)


def test_check_vector_accepts_a_normal_embedding():
    check_vector([0.01] * DIMENSION)
