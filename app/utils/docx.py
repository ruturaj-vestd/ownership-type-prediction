from __future__ import annotations

import re
from zipfile import ZipFile


def read_docx_text(path: str, keep_blank_lines: bool = False) -> str:
    with ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    text = re.sub(r"</w:p>", "\n", xml)
    text = re.sub(r"<.*?>", "", text)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    if keep_blank_lines:
        lines = [ln.strip() for ln in text.splitlines()]
    else:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines).strip()
