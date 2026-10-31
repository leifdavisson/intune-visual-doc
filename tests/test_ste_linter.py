import pytest
from intune_visual_doc.audit.ste_linter import audit_text_ste


def test_ste_sentence_length_warning():
    long_sentence = "This is an extremely long and unnecessarily verbose sentence that goes on and on and contains far more than twenty-five words without stopping for a proper sentence break here."
    issues = audit_text_ste(long_sentence)
    assert any(iss["rule"] == "STE-01: Sentence Length" for iss in issues)


def test_ste_passive_voice_warning():
    passive_sentence = "The security setting was configured by the administrator."
    issues = audit_text_ste(passive_sentence)
    assert any(iss["rule"] == "STE-02: Active Voice" for iss in issues)


def test_ste_unapproved_word_warning():
    complex_sentence = "We utilize BitLocker to protect data."
    issues = audit_text_ste(complex_sentence)
    assert any("utilize" in iss["message"] for iss in issues)


def test_ste_valid_sentences_pass():
    valid = "The administrator configures BitLocker. All laptops use encryption."
    issues = audit_text_ste(valid)
    assert len(issues) == 0
