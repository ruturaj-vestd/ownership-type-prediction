from __future__ import annotations

import base64
import json
import os
import re
import time
from io import BytesIO
from typing import Any

from app.models import CHAgentOutput, WebAgentOutput
from app.utils.http import http_request

CH_BASE_URL = "https://api.company-information.service.gov.uk"
CH_DOC_BASE_URL = "https://document-api.company-information.service.gov.uk"
HTTP_TIMEOUT = 60
CH_FILINGS_PER_PAGE = 80
MAX_DOCS_PER_COMPANY = 8
MAX_PAGES_PER_PDF = 30


def _basic_auth_header(api_key: str) -> dict[str, str]:
    token = base64.b64encode((api_key + ":").encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}


class CompaniesHouseAgent:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("CH_API_KEY")
        if not self.api_key:
            raise RuntimeError("Missing CH_API_KEY env var")

    def ch_get_json(self, path: str, params: dict | None = None) -> dict:
        query = ""
        if params:
            query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{CH_BASE_URL}{path}{query}"
        status, text = http_request("GET", url, headers=_basic_auth_header(self.api_key), timeout=HTTP_TIMEOUT)
        if 200 <= status < 300:
            return json.loads(text)
        return {"error": f"Error {status}", "bodySnippet": (text or "")[:800], "url": url}

    def ch_download_pdf(self, document_id: str, retries: int = 3) -> bytes:
        import urllib.request

        url = f"{CH_DOC_BASE_URL}/document/{document_id}/content"
        headers = _basic_auth_header(self.api_key)
        headers["Accept"] = "application/pdf"
        last = None
        for i in range(retries):
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req, timeout=120) as r:  # noqa: S310
                    return r.read()
            except Exception as exc:
                last = exc
                time.sleep(i + 1)
        raise RuntimeError(f"Failed to download PDF {document_id}: {last}")

    @staticmethod
    def extract_document_id(meta_link: str) -> str | None:
        m = re.search(r"/document/([^/]+)$", meta_link or "")
        return m.group(1) if m else None

    @staticmethod
    def filing_score(item: dict) -> int:
        desc = ((item.get("description") or "") + " " + json.dumps(item.get("description_values") or {})).lower()
        typ = (item.get("type") or "").lower()
        score = 0
        if "psc" in desc or typ.startswith("psc"):
            score += 30
        if "confirmation statement" in desc or typ == "cs01":
            score += 26
        if "statement of capital" in desc or typ == "sh01":
            score += 24
        if "incorporation" in desc or typ == "in01":
            score += 18
        if "accounts" in desc or typ.startswith("aa"):
            score += 10
        if item.get("date"):
            score += 2
        return score

    @staticmethod
    def parse_pdf_text(pdf_bytes: bytes) -> tuple[str, str, list[str]]:
        warnings: list[str] = []
        try:
            from pypdf import PdfReader

            reader = PdfReader(BytesIO(pdf_bytes), strict=False)
            chunks = []
            for page in reader.pages[:MAX_PAGES_PER_PDF]:
                txt = page.extract_text() or ""
                if txt.strip():
                    chunks.append(txt)
            text = "\n".join(chunks).strip()
            if text:
                return "pypdf", text, warnings
            warnings.append("pypdf_extracted_empty_text")
        except Exception as exc:
            warnings.append(f"pypdf_error:{exc}")
        return "none", "", warnings

    @staticmethod
    def extract_psc_facts_from_text(txt: str) -> dict[str, Any]:
        out = {"psc_entity_name": None, "psc_registration_number": None, "control_signals": [], "raw_hits": []}
        m = re.search(r"(RLE\s*Details[\s\S]{0,800}?\bName:\s*([A-Z0-9 &',\.\-]{3,120}))", txt or "", flags=re.I)
        if m:
            out["psc_entity_name"] = re.sub(r"\s+", " ", m.group(2)).strip()
            out["raw_hits"].append("rle_details_name")
        m = re.search(r"\bRegistration\s+Number:\s*([A-Z]{0,2}\d{5,8})\b", txt or "", flags=re.I)
        if m:
            out["psc_registration_number"] = m.group(1).upper()
            out["raw_hits"].append("registration_number_field")
        patterns = [
            ("75%+ shares", r"75%\s*or\s*more.*shares"),
            ("75%+ voting", r"75%\s*or\s*more.*voting\s+rights"),
            ("50%+ shares", r"more\s+than\s+50%.*shares"),
            ("50%+ voting", r"more\s+than\s+50%.*voting\s+rights"),
            ("appoint/remove directors", r"appoint\s+or\s+remove.*majority\s+of\s+the\s+board"),
        ]
        out["control_signals"] = [lbl for lbl, pat in patterns if re.search(pat, txt or "", flags=re.I)]
        return out

    def run(self, web_output: WebAgentOutput) -> CHAgentOutput:
        nums = [str(x).strip().replace(" ", "") for x in web_output.website_company_numbers if str(x).strip()]
        if not nums:
            return CHAgentOutput(ch_evidence_pack={"companies": []}, ch_citations=[], log=["website_company_numbers empty"])

        evidence: dict[str, Any] = {"companies": []}
        citations: list[str] = []
        for cn in nums:
            citations.append(f"https://find-and-update.company-information.service.gov.uk/company/{cn}")
            prof = self.ch_get_json(f"/company/{cn}")
            pscs = self.ch_get_json(f"/company/{cn}/persons-with-significant-control")
            stmts = self.ch_get_json(f"/company/{cn}/persons-with-significant-control-statements")
            offs = self.ch_get_json(f"/company/{cn}/officers")
            filings = self.ch_get_json(f"/company/{cn}/filing-history", {"items_per_page": str(CH_FILINGS_PER_PAGE)})

            docs = []
            for it in sorted((filings.get("items") or []), key=self.filing_score, reverse=True):
                meta = (it.get("links") or {}).get("document_metadata")
                doc_id = self.extract_document_id(meta) if meta else None
                if doc_id:
                    docs.append((it, doc_id))
                if len(docs) >= MAX_DOCS_PER_COMPANY:
                    break

            pdfs = []
            for it, doc_id in docs:
                try:
                    pdf_bytes = self.ch_download_pdf(doc_id)
                    method, text, warns = self.parse_pdf_text(pdf_bytes)
                    facts = self.extract_psc_facts_from_text(text) if text else {}
                except Exception as exc:
                    method, text, warns, facts = "none", "", [f"pdf_download_or_parse_error:{exc}"], {}
                pdfs.append({"document_id": doc_id, "type": it.get("type"), "date": it.get("date"), "description": it.get("description"), "parse_method": method, "warnings": warns, "text_len": len(text or ""), "extracted_text": (text or "")[:80000], "psc_facts": facts})

            evidence["companies"].append({"company_number": cn, "profile": prof, "pscs": pscs, "psc_statements": stmts, "officers": offs, "filings": filings, "downloaded_pdfs": pdfs})

        return CHAgentOutput(
            ch_evidence_pack=evidence,
            ch_citations=citations,
            log=[f"Companies processed: {len(nums)}", f"PDFs downloaded: {sum(len(c['downloaded_pdfs']) for c in evidence['companies'])}", f"PDFs parsed non-empty: {sum(1 for c in evidence['companies'] for p in c['downloaded_pdfs'] if p['text_len'] > 0)}"],
        )
