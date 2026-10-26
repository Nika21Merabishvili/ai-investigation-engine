# tests/test_build_company_docs.py
import pytest

from scripts.build_company_docs import line_kind, parse_source


def test_parse_source_splits_header_and_body():
    meta, body = parse_source("title: Refund runbook\nformat: pdf\nauthor: Ana\n\n# Refunds\n\nStep one.\n")
    assert meta == {"title": "Refund runbook", "format": "pdf", "author": "Ana"}
    assert body == "# Refunds\n\nStep one.\n"


@pytest.mark.parametrize("header", ["format: pdf", "title: X\nformat: xlsx"])
def test_parse_source_rejects_bad_header(header):
    with pytest.raises(ValueError):
        parse_source(header + "\n\nBody text.\n")


def test_line_kind():
    assert line_kind("## Impact") == ("h2", "Impact")
    assert line_kind("- 212 merchants") == ("bullet", "212 merchants")
    assert line_kind("09:40 First duplicate") == ("para", "09:40 First duplicate")
