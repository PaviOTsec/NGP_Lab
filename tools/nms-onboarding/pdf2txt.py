import sys
from pypdf import PdfReader
r = PdfReader(sys.argv[1])
with open(sys.argv[2], "w", encoding="utf-8") as f:
    for i, p in enumerate(r.pages, 1):
        f.write(f"\n<<<PAGE {i}>>>\n" + (p.extract_text() or ""))
print(len(r.pages), "pages")
