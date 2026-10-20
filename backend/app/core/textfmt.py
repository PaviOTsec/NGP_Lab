"""Text conversions that keep commands intact across operating systems.

The clipboard stores text exactly as pasted. These functions produce a *delivery* copy for a
particular destination, and only when asked:

  * line endings  — keep | lf (Linux) | crlf (Windows)
  * sanitize      — replace characters that silently break shells when text has passed
                    through Word/Teams/Outlook/web pages: curly quotes, en/em dashes used as
                    option dashes, non-breaking and zero-width spaces, a stray BOM.
  * encoding      — utf8 | utf8bom (Windows PowerShell 5.1 reads BOM-less .ps1 files as ANSI,
                    which mangles any non-ASCII) | utf16le (with BOM, for legacy tools)

The same rules are mirrored in the clipboard page's JavaScript so "Copy for Linux/Windows"
works without a round-trip; tests pin the Python side.
"""

from __future__ import annotations

import re
from typing import Literal

Eol = Literal["keep", "lf", "crlf"]
Encoding = Literal["utf8", "utf8bom", "utf16le"]

_SANITIZE_MAP = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",  # single curly quotes
    "“": '"', "”": '"', "„": '"', "‟": '"',  # double curly quotes
    "′": "'", "″": '"',                                # primes
    "–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-",  # dashes/minus
    " ": " ", " ": " ", " ": " ", " ": " ",  # non-breaking / thin spaces
    "​": "", "‌": "", "‍": "", "⁠": "", "﻿": "",  # zero-width, BOM
    "…": "...",                                             # ellipsis
}
_SANITIZE_RE = re.compile("|".join(map(re.escape, _SANITIZE_MAP)))


def detect_eol(text: str) -> str:
    """'crlf', 'lf', 'mixed', or 'none' (single line)."""
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    if crlf and lf:
        return "mixed"
    if crlf:
        return "crlf"
    if lf:
        return "lf"
    return "none"


def convert_eol(text: str, eol: Eol) -> str:
    if eol == "keep":
        return text
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.replace("\n", "\r\n") if eol == "crlf" else normalized


def suspicious_chars(text: str) -> int:
    """How many characters `sanitize` would change — shown as a warning badge."""
    return len(_SANITIZE_RE.findall(text))


def sanitize(text: str) -> str:
    return _SANITIZE_RE.sub(lambda m: _SANITIZE_MAP[m.group(0)], text)


def encode(text: str, encoding: Encoding = "utf8") -> bytes:
    if encoding == "utf8bom":
        return b"\xef\xbb\xbf" + text.encode("utf-8")
    if encoding == "utf16le":
        return b"\xff\xfe" + text.encode("utf-16-le")
    return text.encode("utf-8")


def deliver(
    text: str, *, eol: Eol = "keep", do_sanitize: bool = False, encoding: Encoding = "utf8"
) -> bytes:
    """Produce the bytes to hand to a destination."""
    if do_sanitize:
        text = sanitize(text)
    return encode(convert_eol(text, eol), encoding)


def eol_for_os(os_name: str) -> Eol:
    """Default line ending for a target OS (inventory `os`)."""
    return "crlf" if os_name == "windows" else "lf"
