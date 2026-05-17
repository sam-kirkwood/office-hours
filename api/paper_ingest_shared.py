"""Shared paper dedup-and-insert helper.

Called from both /admin/ingest-paper and /ingest-paper-user so that dedup
logic is centralised in one place.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from supabase import Client

logger = logging.getLogger(__name__)


def _is_unique_violation(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code in ("23505", 23505):
        return True
    return "23505" in str(exc) or "duplicate key" in str(exc).lower()


def ingest_paper(
    supabase: Client,
    *,
    title: str,
    authors_json: list[str],
    year: int,
    abstract_md: str,
    arxiv_id: str | None = None,
    doi: str | None = None,
    external_url: str | None = None,
) -> tuple[str, bool]:
    """Dedup-check then insert a paper row.

    Resolution order:
      1. arxiv_id exact match → return existing.
      2. doi exact match → return existing.
      3. Soft check (lower(title), year) when no unique identifier → log
         warning, proceed with insert (two real papers can share a title).
      4. On unique-violation at insert (race), re-select and return existing
         with created=False.

    Returns (paper_id, created). created=False means a duplicate was found and
    the existing row was returned instead of inserting a new one.
    """
    # 1. Dedup by arxiv_id
    if arxiv_id:
        row = (
            supabase.table("papers")
            .select("id")
            .eq("arxiv_id", arxiv_id)
            .limit(1)
            .execute()
        )
        if row.data:
            return row.data[0]["id"], False

    # 2. Dedup by doi
    if doi:
        row = (
            supabase.table("papers")
            .select("id")
            .eq("doi", doi)
            .limit(1)
            .execute()
        )
        if row.data:
            return row.data[0]["id"], False

    # 3. Soft-check by (title, year) when no unique identifier
    if not arxiv_id and not doi:
        soft = (
            supabase.table("papers")
            .select("id, title")
            .ilike("title", title)
            .eq("year", year)
            .limit(1)
            .execute()
        )
        if soft.data:
            logger.warning(
                "Soft-duplicate detected: title=%r year=%d — inserting anyway; "
                "existing paper_id=%s",
                title,
                year,
                soft.data[0]["id"],
            )

    # 4. Insert
    paper_row = {
        "title": title,
        "authors_json": authors_json,
        "year": year,
        "abstract_md": abstract_md,
        "arxiv_id": arxiv_id,
        "doi": doi,
        "external_url": external_url,
    }
    try:
        insert_resp = supabase.table("papers").insert(paper_row).execute()
    except Exception as exc:  # noqa: BLE001
        if not _is_unique_violation(exc):
            raise
        # Race: re-select whichever unique column was violated
        for field, value in [("arxiv_id", arxiv_id), ("doi", doi)]:
            if value:
                row = (
                    supabase.table("papers")
                    .select("id")
                    .eq(field, value)
                    .limit(1)
                    .execute()
                )
                if row.data:
                    return row.data[0]["id"], False
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="unique violation but re-select found nothing",
        ) from exc

    return insert_resp.data[0]["id"], True
