from __future__ import annotations

import base64
import json
import os
import re
import time
from io import BytesIO
from typing import Any
from urllib.parse import urlencode

from app.models import CHAgentOutput, WebAgentOutput
from app.utils.http import http_request

CH_BASE_URL = "https://api.company-information.service.gov.uk"
CH_DOC_BASE_URL = "https://document-api.company-information.service.gov.uk"
HTTP_TIMEOUT = 60
CH_FILINGS_PER_PAGE = 80
MAX_DOCS_PER_COMPANY = 8
MAX_PAGES_PER_PDF = 30
OCR_PAGES = 3
MAX_COMPANIES_TO_PROCESS = 6


def _basic_auth_header(api_key: str) -> dict[str, str]:
    token = base64.b64encode((api_key + ":").encode("utf-8")).decode("utf-8")
    return {"Authorization": f"Basic {token}"}


class CompaniesHouseAgent:
    def __init__(self, api_key: str | None = None):
        self.api_key = "3a812851-46a4-4641-bea7-5e5d6f853abf"
        if not self.api_key:
            raise RuntimeError("Missing CH_API_KEY env var")

    def ch_get_json(self, path: str, params: dict | None = None) -> dict:
        query = f"?{urlencode(params)}" if params else ""
        url = f"{CH_BASE_URL}{path}{query}"
        status, text = http_request("GET", url, headers=_basic_auth_header(self.api_key), timeout=HTTP_TIMEOUT)
        if 200 <= status < 300:
            return json.loads(text)
        return {"error": f"Error {status}", "bodySnippet": (text or "")[:1200], "url": url}

    def search_companies(self, query: str, items_per_page: int = 10) -> dict:
        return self.ch_get_json("/search/companies", {"q": query, "items_per_page": str(items_per_page)})

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
    def extract_company_numbers(text: str) -> list[str]:
        patterns = [r"\b\d{8}\b", r"\bSC\d{6}\b", r"\bNI\d{6}\b", r"\bOC\d{5}\b", r"\bLP\d{6}\b"]
        found: list[str] = []
        for pat in patterns:
            found.extend(re.findall(pat, text or "", flags=re.I))
        clean = []
        seen = set()
        for item in found:
            val = re.sub(r"\s+", "", item).upper()
            if val not in seen:
                seen.add(val)
                clean.append(val)
        return clean

    @staticmethod
    def extract_entity_name_candidates(legal_entity: str) -> list[str]:
        if not legal_entity:
            return []
        hits = re.findall(r"([A-Z][A-Za-z0-9&',\.\-\s]{2,100}\b(?:Limited|Ltd|LLP|PLC))", legal_entity)
        out: list[str] = []
        seen = set()
        for h in hits:
            n = re.sub(r"\s+", " ", h).strip(" ,.;")
            if n and n.lower() not in seen:
                seen.add(n.lower())
                out.append(n)
        return out[:8]

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

        try:
            import fitz

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            chunks = []
            for i in range(min(MAX_PAGES_PER_PDF, doc.page_count)):
                txt = doc.load_page(i).get_text("text") or ""
                if txt.strip():
                    chunks.append(txt)
            text = "\n".join(chunks).strip()
            if text:
                return "pymupdf", text, warnings
            warnings.append("pymupdf_extracted_empty_text")
        except Exception as exc:
            warnings.append(f"pymupdf_error:{exc}")

        try:
            import fitz
            import pytesseract
            from PIL import Image

            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            chunks = []
            for i in range(min(OCR_PAGES, doc.page_count, MAX_PAGES_PER_PDF)):
                pix = doc.load_page(i).get_pixmap(dpi=220)
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                txt = pytesseract.image_to_string(img) or ""
                if txt.strip():
                    chunks.append(txt)
            text = "\n".join(chunks).strip()
            if text:
                warnings.append("ocr_used")
                return "ocr", text, warnings
            warnings.append("ocr_extracted_empty_text")
        except Exception as exc:
            warnings.append(f"ocr_failed:{exc}")

        return "none", "", warnings

    @staticmethod
    def extract_psc_facts_from_text(txt: str) -> dict[str, Any]:
        out = {"psc_entity_name": None, "psc_registration_number": None, "control_signals": [], "raw_hits": []}
        t = txt or ""
        m = re.search(r"(RLE\s*Details[\s\S]{0,800}?\bName:\s*([A-Z0-9 &',\.\-]{3,120}))", t, flags=re.I)
        if m:
            out["psc_entity_name"] = re.sub(r"\s+", " ", m.group(2)).strip()
            out["raw_hits"].append("rle_details_name")
        if not out["psc_entity_name"]:
            m = re.search(r"(registrable\s+RLE[\s\S]{0,500}?\bName:\s*([A-Z0-9 &',\.\-]{3,120}))", t, flags=re.I)
            if m:
                out["psc_entity_name"] = re.sub(r"\s+", " ", m.group(2)).strip()
                out["raw_hits"].append("registrable_rle_name")
        m = re.search(r"\bRegistration\s+Number:\s*([A-Z]{0,2}\d{5,8})\b", t, flags=re.I)
        if m:
            out["psc_registration_number"] = m.group(1).strip().upper()
            out["raw_hits"].append("registration_number_field")

        patterns = [
            ("75%+ shares", r"75%\s*or\s*more.*shares"),
            ("75%+ voting", r"75%\s*or\s*more.*voting\s+rights"),
            ("50%+ shares", r"more\s+than\s+50%.*shares"),
            ("50%+ voting", r"more\s+than\s+50%.*voting\s+rights"),
            ("appoint/remove directors", r"appoint\s+or\s+remove.*majority\s+of\s+the\s+board"),
        ]
        out["control_signals"] = [lbl for lbl, pat in patterns if re.search(pat, t, flags=re.I)]

        company_name_match = re.search(r"Company\s+Name:\s*([A-Z0-9 &',\.\-]{3,120})", t, flags=re.I)
        if company_name_match and out["psc_entity_name"]:
            co_name = re.sub(r"\s+", " ", company_name_match.group(1)).strip()
            if out["psc_entity_name"].upper() == co_name.upper():
                out["raw_hits"].append("psc_name_equals_company_name_suspect")
        return out

    @staticmethod
    def _psc_item_control_score(psc_item: dict[str, Any]) -> int:
        score = 0
        for noc in (psc_item.get("natures_of_control") or []):
            s = str(noc).lower()
            if "75" in s:
                score += 8
            elif "50" in s:
                score += 6
            elif "25" in s:
                score += 4
            elif "appoint" in s or "remove" in s:
                score += 7
            else:
                score += 2
        if psc_item.get("ceased_on"):
            score -= 4
        return score

    def summarize_highest_holder(self, company_record: dict[str, Any]) -> dict[str, Any]:
        psc_items = (company_record.get("pscs") or {}).get("items") or []
        best = None
        best_score = -10_000
        for item in psc_items:
            s = self._psc_item_control_score(item)
            if s > best_score:
                best = item
                best_score = s

        summary = {
            "highest_holder": None,
            "holder_kind": None,
            "control_basis": [],
            "source": "none",
            "confidence": 0.25,
        }
        if best:
            summary.update(
                {
                    "highest_holder": best.get("name") or (best.get("name_elements") or {}).get("forename"),
                    "holder_kind": best.get("kind"),
                    "control_basis": best.get("natures_of_control") or [],
                    "source": "ch_psc_api",
                    "confidence": 0.8 if (best.get("natures_of_control") or []) else 0.65,
                }
            )
            return summary

        for pdf in (company_record.get("downloaded_pdfs") or []):
            facts = pdf.get("psc_facts") or {}
            if facts.get("psc_entity_name"):
                summary.update(
                    {
                        "highest_holder": facts.get("psc_entity_name"),
                        "holder_kind": "pdf_extracted",
                        "control_basis": facts.get("control_signals") or [],
                        "source": "ch_psc_pdf",
                        "confidence": 0.55,
                    }
                )
                return summary

        return summary

    def resolve_company_numbers(self, web_output: WebAgentOutput) -> tuple[list[str], list[str]]:
        logs: list[str] = []
        resolved = [str(x).strip().replace(" ", "") for x in web_output.website_company_numbers if str(x).strip()]

        if resolved:
            logs.append(f"website_company_numbers provided: {resolved}")

        # fallback 1: extract company numbers from legal entity string
        legal_text_nums = self.extract_company_numbers(web_output.legal_entity)
        for n in legal_text_nums:
            if n not in resolved:
                resolved.append(n)
        if legal_text_nums:
            logs.append(f"numbers extracted from legal_entity: {legal_text_nums}")

        # fallback 2: CH search by company + legal entity candidates
        queries = [web_output.company]
        queries.extend(self.extract_entity_name_candidates(web_output.legal_entity))
        for q in queries:
            if not q:
                continue
            search = self.search_companies(q)
            items = search.get("items") or []
            if items:
                logs.append(f"search '{q}' returned {len(items)} items")
            for it in items[:5]:
                num = str(it.get("company_number") or "").strip().upper()
                title = str(it.get("title") or "")
                if not num:
                    continue
                if num not in resolved:
                    resolved.append(num)
                logs.append(f"candidate from search: {num} ({title})")

        # de-dupe + cap
        deduped = []
        seen = set()
        for n in resolved:
            if n and n not in seen:
                seen.add(n)
                deduped.append(n)
        return deduped[:MAX_COMPANIES_TO_PROCESS], logs

    def run(self, web_output: WebAgentOutput) -> CHAgentOutput:
        nums, resolution_logs = self.resolve_company_numbers(web_output)
        if not nums:
            return CHAgentOutput(ch_evidence_pack={"companies": [], "ownership_summary": {}}, ch_citations=[], log=resolution_logs + ["no company numbers resolved"])

        evidence: dict[str, Any] = {"companies": []}
        citations: list[str] = []

        for cn in nums:
            citations.append(f"https://find-and-update.company-information.service.gov.uk/company/{cn}")

            prof = self.ch_get_json(f"/company/{cn}")
            pscs = self.ch_get_json(f"/company/{cn}/persons-with-significant-control")
            stmts = self.ch_get_json(f"/company/{cn}/persons-with-significant-control-statements")
            offs = self.ch_get_json(f"/company/{cn}/officers")
            filings = self.ch_get_json(f"/company/{cn}/filing-history", {"items_per_page": str(CH_FILINGS_PER_PAGE)})

            items = filings.get("items") or []
            docs: list[tuple[dict[str, Any], str]] = []
            for it in sorted(items, key=self.filing_score, reverse=True):
                meta = (it.get("links") or {}).get("document_metadata")
                doc_id = self.extract_document_id(meta) if meta else None
                if not doc_id:
                    continue
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

                pdfs.append(
                    {
                        "document_id": doc_id,
                        "type": it.get("type"),
                        "date": it.get("date"),
                        "description": it.get("description"),
                        "parse_method": method,
                        "warnings": warns,
                        "text_len": len(text or ""),
                        "extracted_text": (text or "")[:80000],
                        "psc_facts": facts,
                    }
                )

            company_record = {
                "company_number": cn,
                "profile": prof,
                "pscs": pscs,
                "psc_statements": stmts,
                "officers": offs,
                "filings": filings,
                "downloaded_pdfs": pdfs,
            }
            company_record["highest_ownership_holder"] = self.summarize_highest_holder(company_record)
            evidence["companies"].append(company_record)

        # global ownership best-effort summary
        global_best = {"highest_holder": None, "source_company_number": None, "control_basis": [], "confidence": 0.0}
        for c in evidence["companies"]:
            h = c.get("highest_ownership_holder") or {}
            if float(h.get("confidence") or 0) > float(global_best.get("confidence") or 0):
                global_best = {
                    "highest_holder": h.get("highest_holder"),
                    "source_company_number": c.get("company_number"),
                    "control_basis": h.get("control_basis") or [],
                    "confidence": h.get("confidence") or 0.0,
                }
        evidence["ownership_summary"] = global_best

        return CHAgentOutput(
            ch_evidence_pack=evidence,
            ch_citations=citations,
            log=resolution_logs
            + [
                f"Companies processed: {len(nums)}",
                f"PDFs downloaded: {sum(len(c['downloaded_pdfs']) for c in evidence['companies'])}",
                f"PDFs parsed non-empty: {sum(1 for c in evidence['companies'] for p in c['downloaded_pdfs'] if p['text_len'] > 0)}",
                f"Top holder: {global_best.get('highest_holder') or '[none]'}",
            ],
        )
