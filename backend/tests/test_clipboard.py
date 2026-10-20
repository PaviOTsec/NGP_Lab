"""Shared clipboard: formatting rules, the store, and the HTTP board API."""

from __future__ import annotations

import hashlib
import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import textfmt
from app.core.audit import AuditLog
from app.core.clipstore import ClipError, ClipStore
from app.routes import board

# --- textfmt -------------------------------------------------------------------------------


def test_detect_eol():
    assert textfmt.detect_eol("a\r\nb\r\n") == "crlf"
    assert textfmt.detect_eol("a\nb\n") == "lf"
    assert textfmt.detect_eol("a\r\nb\n") == "mixed"
    assert textfmt.detect_eol("one line") == "none"


def test_convert_eol_roundtrip_keeps_tabs_and_blank_lines():
    src = "if x:\n\tdo()\n\n\tdone()\n"
    crlf = textfmt.convert_eol(src, "crlf")
    assert crlf == "if x:\r\n\tdo()\r\n\r\n\tdone()\r\n"
    assert textfmt.convert_eol(crlf, "lf") == src
    assert textfmt.convert_eol("a\r\nb\nc", "crlf") == "a\r\nb\r\nc"  # mixed -> uniform


def test_sanitize_fixes_word_damage_only():
    damaged = "Get-Service \u2013Name \u201cWinRM\u201d\u00a0| fl\u200b"
    assert textfmt.sanitize(damaged) == 'Get-Service -Name "WinRM" | fl'
    assert textfmt.suspicious_chars(damaged) == 5
    assert textfmt.sanitize("plain 'text' -x") == "plain 'text' -x"


def test_encodings():
    assert textfmt.encode("a", "utf8bom") == b"\xef\xbb\xbfa"
    assert textfmt.encode("a", "utf16le") == b"\xff\xfea\x00"
    assert textfmt.deliver("x\ny", eol="crlf", encoding="utf8") == b"x\r\ny"


# --- store ---------------------------------------------------------------------------------


def test_store_text_is_byte_exact(tmp_path):
    s = ClipStore(tmp_path)
    text = "#!/bin/bash\r\n\techo 'hi'  \r\n\r\n"
    item = s.add_text("main", text, origin="10.1.20.5")
    assert s.read_bytes("main", item.id) == text.encode()
    assert item.sha256 == hashlib.sha256(text.encode()).hexdigest()
    assert item.eol == "crlf" and item.lines == 3


def test_store_file_and_limits(tmp_path):
    s = ClipStore(tmp_path, max_items=2, max_file_bytes=10)
    a = s.add_file("main", "../../evil\\name.bin", io.BytesIO(b"\x00\x01"))
    assert a.name == "name.bin" and s.read_bytes("main", a.id) == b"\x00\x01"
    with pytest.raises(ClipError):
        s.add_file("main", "big", io.BytesIO(b"x" * 11))
    s.add_text("main", "b")
    s.add_text("main", "c")
    assert [i.kind for i in s.list("main")] == ["text", "text"]  # oldest dropped at max_items


def test_board_names_are_validated(tmp_path):
    with pytest.raises(ClipError):
        ClipStore(tmp_path).add_text("../x", "nope")


# --- HTTP ----------------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path):
    store = ClipStore(tmp_path / "clip")
    app = FastAPI()
    app.include_router(board.make_router(store, AuditLog(tmp_path / "audit.jsonl"),
                                         inline_text_bytes=1024, serve_page=True))
    return TestClient(app)


def test_post_text_raw_keeps_exact_bytes(client):
    body = "line1\r\n\tline2\n".encode()
    r = client.post("/api/clip/main/text?name=x.sh", content=body)
    assert r.status_code == 200
    item = r.json()
    assert item["eol"] == "mixed"
    raw = client.get(f"/r/main/{item['id']}")
    assert raw.content == body
    assert raw.headers["x-clip-sha256"] == hashlib.sha256(body).hexdigest()


def test_raw_delivery_conversions(client):
    client.post("/api/clip/main/text", content="a\nb \u201cq\u201d\n".encode())
    assert client.get("/r/main?eol=crlf").content == "a\r\nb \u201cq\u201d\r\n".encode()
    assert client.get("/r/main?eol=lf&sanitize=1").content == b'a\nb "q"\n'
    assert client.get("/r/main?encoding=utf8bom").content.startswith(b"\xef\xbb\xbf")


def test_powershell_cp1252_and_utf16_bodies_decode(client):
    r = client.post("/api/clip/main/text", content="caf\u00e9".encode("cp1252"))
    assert client.get(f"/r/main/{r.json()['id']}").text == "caf\u00e9"
    r = client.post("/api/clip/main/text", content="hi".encode("utf-16"))  # BOM + UTF-16LE
    assert client.get(f"/r/main/{r.json()['id']}").text == "hi"


def test_file_upload_raw_and_multipart(client):
    payload = bytes(range(256)) * 10
    r = client.post("/api/clip/main/upload?name=blob.bin", content=payload)
    assert client.get(f"/r/main/{r.json()['id']}").content == payload
    r = client.post("/api/clip/main/files", files=[("files", ("a.txt", b"A\r\n")),
                                                   ("files", ("b.bin", b"\x00"))])
    assert [i["name"] for i in r.json()["items"]] == ["a.txt", "b.bin"]
    assert client.get(f"/r/main/{r.json()['items'][0]['id']}?eol=lf").content == b"A\r\n"  # files untouched


def test_list_version_delete_and_page(client):
    v0 = client.get("/api/clip/main/version").json()["version"]
    item = client.post("/api/clip/main/text", content=b"hello").json()
    listing = client.get("/api/clip/main").json()
    assert listing["version"] != v0 and listing["items"][0]["text"] == "hello"
    assert client.delete(f"/api/clip/main/{item['id']}").status_code == 200
    assert client.get("/api/clip/main").json()["items"] == []
    assert client.get(f"/r/main/{item['id']}").status_code == 404
    page = client.get("/b/main")
    assert page.status_code == 200 and "Lab Clipboard" in page.text
    assert client.get("/b/..%2F..").status_code in (400, 404)
