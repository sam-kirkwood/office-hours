"""POST /ingest-paper-user — user-provided paper ingestion.

Accepts an arXiv URL/ID, DOI, or bare title from the daily view.

Flow:
  1. Auth check.
  2. Parse raw_input: arXiv URL/ID → extract arXiv ID; DOI pattern → DOI path;
     else → bare-title path.
  3. arXiv path: fetch export.arxiv.org API, parse Atom feed.
     DOI path: fetch api.crossref.org, parse JSON.
     Bare-title path: ILIKE search; insert with sparse metadata if not found.
     Both network fetches fall back to sparse-metadata insert on error.
  4. Call ingest_paper(...) → (paper_id, created).
  5. Call generate_engagement_for_paper(...) → engagement_id.
  6. Insert queue_items row (priority 0.8 — user-initiated).
  7. Return IngestPaperUserResponse.
"""

from __future__ import annotations

import logging
import re
from uuid import UUID
from xml.etree import ElementTree as ET

import httpx
from anthropic import Anthropic
from fastapi import APIRouter, Depends
from supabase import Client

from anthropic_client import get_anthropic_client
from auth import require_internal_token
from paper_ingest_shared import ingest_paper
from routes.generate_paper_engagement import generate_engagement_for_paper
from schemas import IngestPaperUserRequest, IngestPaperUserResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
router = APIRouter()

_ARXIV_URL_RE = re.compile(
    r"arxiv\.org/abs/([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)", re.IGNORECASE
)
_ARXIV_ID_RE = re.compile(r"^([0-9]{4}\.[0-9]{4,5}(?:v\d+)?)$")
_DOI_RE = re.compile(r"(10\.\d{4,}/\S+)")

_ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _strip_version(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id)


def _fetch_arxiv(arxiv_id: str) -> dict:
    """Fetch metadata from the arXiv API. Returns a metadata dict."""
    canonical_id = _strip_version(arxiv_id)
    url = f"https://export.arxiv.org/api/query?id_list={canonical_id}"
    r = httpx.get(url, timeout=10.0, follow_redirects=True)
    r.raise_for_status()

    root = ET.fromstring(r.text)
    entry = root.find(f"{_ATOM_NS}entry")
    if entry is None:
        raise ValueError(f"arXiv ID {arxiv_id} not found in API response")

    title = (entry.findtext(f"{_ATOM_NS}title") or "").strip().replace("\n", " ")
    summary = (entry.findtext(f"{_ATOM_NS}summary") or "").strip()
    published = entry.findtext(f"{_ATOM_NS}published") or ""
    year = int(published[:4]) if len(published) >= 4 else 0

    authors = [
        (el.findtext(f"{_ATOM_NS}name") or "").strip()
        for el in entry.findall(f"{_ATOM_NS}author")
        if (el.findtext(f"{_ATOM_NS}name") or "").strip()
    ]

    return {
        "title": title,
        "authors_json": authors,
        "year": year,
        "abstract_md": summary,
        "arxiv_id": canonical_id,
    }


def _fetch_crossref(doi: str) -> dict:
    """Fetch metadata from the CrossRef API. Returns a metadata dict."""
    url = f"https://api.crossref.org/works/{doi}"
    r = httpx.get(
        url,
        timeout=10.0,
        follow_redirects=True,
        headers={"User-Agent": "office-hours/1.0 (mailto:support@example.com)"},
    )
    r.raise_for_status()

    msg = r.json().get("message", {})

    title_list = msg.get("title", [])
    title = title_list[0] if title_list else ""

    raw_abstract = msg.get("abstract", "")
    abstract = re.sub(r"<[^>]+>", "", raw_abstract).strip()

    authors = []
    for a in msg.get("author", []):
        parts = [a.get("family", ""), a.get("given", "")]
        name = ", ".join(p for p in parts if p)
        if name:
            authors.append(name)

    year = 0
    for date_key in ("published-print", "published-online", "issued"):
        date_parts = msg.get(date_key, {}).get("date-parts", [])
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
            break

    return {
        "title": title,
        "authors_json": authors,
        "year": year,
        "abstract_md": abstract,
        "doi": doi,
    }


def _resolve(
    supabase: Client,
    raw_input: str,
) -> tuple[dict, str | None]:
    """Parse raw_input and resolve metadata.

    Returns (meta_dict, paper_id_if_already_found).
    paper_id_if_already_found is non-None only for bare-title ILIKE matches
    where we skip ingest_paper() and use the existing row directly.
    """
    # 1. arXiv URL
    m = _ARXIV_URL_RE.search(raw_input)
    if m:
        arxiv_id = m.group(1)
        try:
            return _fetch_arxiv(arxiv_id), None
        except Exception:
            logger.warning("arXiv fetch failed for %s; using sparse metadata", arxiv_id)
            return {"title": raw_input, "authors_json": [], "year": 0, "abstract_md": "",
                    "arxiv_id": _strip_version(arxiv_id)}, None

    # 2. Bare arXiv ID
    m = _ARXIV_ID_RE.match(raw_input)
    if m:
        arxiv_id = m.group(1)
        try:
            return _fetch_arxiv(arxiv_id), None
        except Exception:
            logger.warning("arXiv fetch failed for %s; using sparse metadata", arxiv_id)
            return {"title": raw_input, "authors_json": [], "year": 0, "abstract_md": "",
                    "arxiv_id": _strip_version(arxiv_id)}, None

    # 3. DOI (may appear bare or inside a doi.org URL)
    m = _DOI_RE.search(raw_input)
    if m:
        doi = m.group(1)
        try:
            return _fetch_crossref(doi), None
        except Exception:
            logger.warning("CrossRef fetch failed for %s; using sparse metadata", doi)
            return {"title": raw_input, "authors_json": [], "year": 0, "abstract_md": "",
                    "doi": doi}, None

    # 4. Bare title — ILIKE search first
    existing = (
        supabase.table("papers")
        .select("id")
        .ilike("title", f"%{raw_input}%")
        .limit(1)
        .execute()
    )
    if existing.data:
        return {}, existing.data[0]["id"]

    # No match — insert with sparse metadata
    logger.warning("Bare-title insert for %r — metadata will be sparse", raw_input)
    return {"title": raw_input, "authors_json": [], "year": 0, "abstract_md": ""}, None


@router.post(
    "/ingest-paper-user",
    response_model=IngestPaperUserResponse,
    dependencies=[Depends(require_internal_token)],
)
def ingest_paper_user(
    body: IngestPaperUserRequest,
    supabase: Client = Depends(get_supabase_client),
    anthropic: Anthropic = Depends(get_anthropic_client),
) -> IngestPaperUserResponse:
    user_id = str(body.user_id)
    raw_input = body.raw_input.strip()

    meta, found_paper_id = _resolve(supabase, raw_input)

    if found_paper_id:
        # Bare-title ILIKE match: paper already exists, skip insert
        paper_id = found_paper_id
        created = False
    else:
        paper_id, created = ingest_paper(
            supabase,
            title=meta.get("title") or raw_input,
            authors_json=meta.get("authors_json", []),
            year=meta.get("year", 0),
            abstract_md=meta.get("abstract_md", ""),
            arxiv_id=meta.get("arxiv_id"),
            doi=meta.get("doi"),
        )

    # Generate paper engagement
    engagement_id = generate_engagement_for_paper(
        supabase=supabase,
        anthropic=anthropic,
        user_id=user_id,
        paper_id=paper_id,
    )

    # Insert queue item (high priority — user-initiated)
    display_title = meta.get("title") or raw_input
    queue_resp = (
        supabase.table("queue_items")
        .insert(
            {
                "user_id": user_id,
                "kind": "paper_engagement",
                "ref_id": engagement_id,
                "state": "pending",
                "priority_score": 0.8,
                "added_reason": f"A paper you added: {display_title}",
                "time_estimate_minutes_low": 20,
                "time_estimate_minutes_high": 45,
            }
        )
        .execute()
    )
    queue_item_id = queue_resp.data[0]["id"]

    return IngestPaperUserResponse(
        paper_id=UUID(paper_id),
        queue_item_id=UUID(queue_item_id),
        created=created,
        engagement_id=UUID(engagement_id),
    )
