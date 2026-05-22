"""Unit tests for the OnlyOffice-backed PDF converter.

OnlyOffice itself isn't reachable from the test env, so we
monkey-patch ``httpx.Client`` with a fake that records request bodies
and serves back canned conversion responses. Anything that actually
exercises OnlyOffice belongs in an integration check against a
running container, not here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
import jwt as pyjwt
import pytest

from app.core import office_convert
from app.core.config import settings


JOB_ID = 7


@pytest.fixture
def source(tmp_path) -> Path:
    f = tmp_path / "deck.pptx"
    f.write_bytes(b"PK\x03\x04 fake pptx bytes")
    return f


@pytest.fixture
def output(tmp_path) -> Path:
    return tmp_path / "deck.pptx.preview.pdf"


@pytest.fixture
def configured(monkeypatch):
    """Most tests need both URLs set so convert_to_pdf actually tries."""
    monkeypatch.setattr(settings, "onlyoffice_internal_url", "http://onlyoffice")
    monkeypatch.setattr(settings, "backend_internal_url", "http://backend:8000")
    monkeypatch.setattr(settings, "onlyoffice_jwt_secret", "test-secret")


class FakeResponse:
    def __init__(self, status_code: int, *, json_body: Any | None = None, body: bytes = b""):
        self.status_code = status_code
        self._json = json_body
        self.content = body

    def json(self):
        if self._json is None:
            raise ValueError("no json body")
        return self._json


class FakeClient:
    """Minimal stand-in for httpx.Client used in convert_to_pdf.

    Tests assemble a sequence of (method, url_predicate, response)
    triples; each call advances through the queue and asserts the
    request matches. Anything off-script is a test failure."""

    def __init__(self, script):
        self._script = list(script)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def _next(self, method, url):
        if not self._script:
            raise AssertionError(f"unexpected {method} {url}")
        expected_method, expected_url_check, response = self._script.pop(0)
        assert method == expected_method, (
            f"expected {expected_method} {expected_url_check}, got {method} {url}"
        )
        assert expected_url_check(url), f"url assertion failed for {url}"
        return response

    def post(self, url, *, json=None, headers=None):
        self.calls.append({"method": "POST", "url": url, "json": json, "headers": headers})
        return self._next("POST", url)

    def get(self, url):
        self.calls.append({"method": "GET", "url": url})
        return self._next("GET", url)


# ---------- is_convertible ----------


def test_is_convertible_recognizes_office_extensions():
    assert office_convert.is_convertible("a.docx")
    assert office_convert.is_convertible("a.DOCX")
    assert office_convert.is_convertible("a.doc")
    assert office_convert.is_convertible("a.ppt")
    assert office_convert.is_convertible("a.pptx")


def test_is_convertible_rejects_non_office():
    assert not office_convert.is_convertible("a.pdf")
    assert not office_convert.is_convertible("a.png")
    assert not office_convert.is_convertible("a.xlsx")
    assert not office_convert.is_convertible("a")


# ---------- convert_to_pdf — happy path ----------


def test_convert_to_pdf_signs_request_and_writes_returned_pdf(
    source, output, configured, monkeypatch
):
    convert_response = FakeResponse(
        200,
        json_body={"endConvert": True, "fileUrl": "http://onlyoffice/cache/files/abc.pdf"},
    )
    pdf_response = FakeResponse(200, body=b"%PDF-1.4 fake bytes")

    fake = FakeClient([
        ("POST", lambda u: u == "http://onlyoffice/ConvertService.ashx", convert_response),
        ("GET", lambda u: u == "http://onlyoffice/cache/files/abc.pdf", pdf_response),
    ])
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: fake)

    assert office_convert.convert_to_pdf(JOB_ID, source, output) is True
    assert output.read_bytes() == b"%PDF-1.4 fake bytes"

    # Inspect the POST: filetype/outputtype set right, async polling
    # mode is used, the body carries a JWT we can decode with the
    # shared secret, and the source URL points at our internal endpoint.
    post = fake.calls[0]
    body = post["json"]
    assert body["filetype"] == "pptx"
    assert body["outputtype"] == "pdf"
    assert body["async"] is True
    assert body["url"].startswith("http://backend:8000/internal/source/7/")
    assert "token" in body
    decoded = pyjwt.decode(body["token"], "test-secret", algorithms=["HS256"])
    assert decoded["filetype"] == "pptx"
    assert decoded["outputtype"] == "pdf"
    assert post["headers"]["Authorization"].startswith("Bearer ")
    # OnlyOffice's ConvertService.ashx defaults to XML responses; the
    # Accept header is what flips it to JSON. Without this we'd silently
    # fail every conversion at resp.json().
    assert post["headers"]["Accept"] == "application/json"


def test_convert_to_pdf_polls_until_endconvert_true(
    source, output, configured, monkeypatch
):
    """Async mode: OnlyOffice answers some polls with endConvert=false
    while the conversion is in flight. We keep polling with the same
    key until it flips to true."""
    monkeypatch.setattr(office_convert, "POLL_INTERVAL_SECONDS", 0.0)

    in_flight = FakeResponse(200, json_body={"endConvert": False, "percent": 30})
    done = FakeResponse(
        200,
        json_body={"endConvert": True, "fileUrl": "http://onlyoffice/cache/files/x.pdf"},
    )
    pdf = FakeResponse(200, body=b"%PDF")

    fake = FakeClient([
        ("POST", lambda u: True, in_flight),
        ("POST", lambda u: True, in_flight),
        ("POST", lambda u: True, done),
        ("GET", lambda u: True, pdf),
    ])
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: fake)

    assert office_convert.convert_to_pdf(JOB_ID, source, output) is True

    # The same conversion key sticks across polls — otherwise OnlyOffice
    # would treat each request as a new job and never return a fileUrl.
    keys = {call["json"]["key"] for call in fake.calls if call["method"] == "POST"}
    assert len(keys) == 1


def test_convert_to_pdf_returns_false_when_polling_exceeds_deadline(
    source, output, configured, monkeypatch
):
    # 5ms poll interval + 20ms deadline → ~3–4 iterations before we
    # short-circuit on the deadline guard. Script size comfortably
    # outlasts that so the loop trips on the deadline, not on
    # running out of canned responses.
    monkeypatch.setattr(office_convert, "POLL_INTERVAL_SECONDS", 0.005)
    monkeypatch.setattr(settings, "onlyoffice_convert_timeout_seconds", 0.02)

    fake = FakeClient([
        ("POST", lambda u: True, FakeResponse(200, json_body={"endConvert": False})),
    ] * 200)
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: fake)

    assert office_convert.convert_to_pdf(JOB_ID, source, output) is False


def test_convert_to_pdf_url_encodes_filename(
    output, configured, monkeypatch, tmp_path
):
    """Unicode filenames have to survive the round-trip to OnlyOffice
    intact — the documentserver reaches our internal endpoint via the
    URL it sees in the request body, so a raw 簡報.pptx would explode
    in the HTTP line. Percent-encoding the path segment keeps that
    safe."""
    src = tmp_path / "簡報.pptx"
    src.write_bytes(b"x")
    done = FakeResponse(
        200,
        json_body={"endConvert": True, "fileUrl": "http://onlyoffice/cache/x.pdf"},
    )
    fake = FakeClient([
        ("POST", lambda u: True, done),
        ("GET", lambda u: True, FakeResponse(200, body=b"%PDF")),
    ])
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: fake)

    assert office_convert.convert_to_pdf(JOB_ID, src, output) is True

    posted_url = fake.calls[0]["json"]["url"]
    assert "%E7%B0%A1%E5%A0%B1" in posted_url
    assert "簡報" not in posted_url


# ---------- convert_to_pdf — failure modes ----------


def test_convert_to_pdf_returns_false_when_config_missing(
    source, output, monkeypatch
):
    monkeypatch.setattr(settings, "onlyoffice_internal_url", "")
    assert office_convert.convert_to_pdf(JOB_ID, source, output) is False


def test_convert_to_pdf_returns_false_when_source_missing(
    tmp_path, output, configured
):
    assert (
        office_convert.convert_to_pdf(JOB_ID, tmp_path / "nope.docx", output) is False
    )


def test_convert_to_pdf_rejects_non_office_source(
    tmp_path, output, configured
):
    source = tmp_path / "x.png"
    source.write_bytes(b"PNG")
    assert office_convert.convert_to_pdf(JOB_ID, source, output) is False


def test_convert_to_pdf_returns_false_on_non_200_post(
    source, output, configured, monkeypatch
):
    fake = FakeClient([
        ("POST", lambda u: True, FakeResponse(500)),
    ])
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: fake)

    assert office_convert.convert_to_pdf(JOB_ID, source, output) is False
    assert not output.exists()


def test_convert_to_pdf_returns_false_on_onlyoffice_error_code(
    source, output, configured, monkeypatch
):
    fake = FakeClient([
        ("POST", lambda u: True, FakeResponse(200, json_body={"error": -8})),
    ])
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: fake)

    assert office_convert.convert_to_pdf(JOB_ID, source, output) is False


def test_convert_to_pdf_returns_false_when_endconvert_true_but_fileurl_missing(
    source, output, configured, monkeypatch
):
    fake = FakeClient([
        ("POST", lambda u: True, FakeResponse(200, json_body={"endConvert": True})),
    ])
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: fake)

    assert office_convert.convert_to_pdf(JOB_ID, source, output) is False


def test_convert_to_pdf_returns_false_on_pdf_fetch_failure(
    source, output, configured, monkeypatch
):
    fake = FakeClient([
        ("POST", lambda u: True, FakeResponse(200, json_body={"endConvert": True, "fileUrl": "http://x/y"})),
        ("GET", lambda u: True, FakeResponse(404)),
    ])
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: fake)

    assert office_convert.convert_to_pdf(JOB_ID, source, output) is False
    assert not output.exists()


def test_convert_to_pdf_returns_false_on_network_error(
    source, output, configured, monkeypatch
):
    class BoomClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, *_a, **_k):
            raise httpx.ConnectError("backend dead")

        def get(self, *_a, **_k):
            raise httpx.ConnectError("backend dead")

    monkeypatch.setattr(httpx, "Client", lambda *a, **k: BoomClient())

    assert office_convert.convert_to_pdf(JOB_ID, source, output) is False
