import pytest

from pipeline.clean import clean_document
from pipeline.files import EXPECTED_PATH, load_raw_docs, read_json
from pipeline.validate import document_checks, validate_corpus

EXPECTED = read_json(EXPECTED_PATH)


@pytest.fixture(scope="module")
def reports():
    _, reports = validate_corpus(load_raw_docs())
    return {r.id: r for r in reports}


@pytest.mark.parametrize("doc_id", sorted(EXPECTED))
def test_synthetic_document_fails_exactly_its_expected_check(reports, doc_id):
    failed = {c.name for c in reports[doc_id].checks if not c.passed}
    assert failed == {EXPECTED[doc_id]["check"]}


def test_real_articles_pass_every_check(reports):
    real = [r for r in reports.values() if r.source != "synthetic"]
    assert len(real) == 40
    failing = {r.id: [c.name for c in r.checks if not c.passed] for r in real}
    assert {k: v for k, v in failing.items() if v} == {}


def test_pii_is_flagged_not_quarantined(reports):
    pii = reports["synthetic-pii"]
    assert pii.flagged == ["pii"]
    assert not pii.quarantined


def test_all_synthetic_problems_except_pii_are_quarantined(reports):
    quarantined = {r.id for r in reports.values() if r.quarantined}
    assert quarantined == set(EXPECTED) - {"synthetic-pii"}


def test_pasted_mojibake_stub_fails_mojibake_and_min_length():
    raw = {"id": "pasted", "title": "t", "source": "pasted", "url": "", "license": "", "text": "Ã©Ã© short"}
    failed = {c.name for c in document_checks(raw, clean_document(raw)) if not c.passed}
    assert failed == {"mojibake", "min_length"}
