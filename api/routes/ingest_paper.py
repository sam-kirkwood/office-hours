"""POST /admin/ingest-paper — ingest a paper for engagement generation.

Flow:
  1. Auth check (internal token — operator only).
  2. Dedup by arxiv_id then doi. On match return existing row, created=False.
  3. Soft-check (lower(title), year) when no unique identifier — log warning, proceed.
  4. Insert into papers. On unique-violation re-select and return created=False.
  5. Return IngestPaperResponse.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client

from auth import require_internal_token
from schemas import IngestPaperRequest, IngestPaperResponse
from supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter()


def _is_unique_violation(exc: Exception) -> bool:
    code = getattr(exc, "code", None)
    if code in ("23505", 23505):
        return True
    return "23505" in str(exc) or "duplicate key" in str(exc).lower()


@router.post(
    "/admin/ingest-paper",
    response_model=IngestPaperResponse,
    dependencies=[Depends(require_internal_token)],
)
def ingest_paper(
    body: IngestPaperRequest,
    supabase: Client = Depends(get_supabase_client),
) -> IngestPaperResponse:
    # 2. Dedup by arxiv_id
    if body.arxiv_id:
        row = (
            supabase.table("papers")
            .select("id")
            .eq("arxiv_id", body.arxiv_id)
            .limit(1)
            .execute()
        )
        if row.data:
            return IngestPaperResponse(paper_id=UUID(row.data[0]["id"]), created=False)

    # Dedup by doi
    if body.doi:
        row = (
            supabase.table("papers")
            .select("id")
            .eq("doi", body.doi)
            .limit(1)
            .execute()
        )
        if row.data:
            return IngestPaperResponse(paper_id=UUID(row.data[0]["id"]), created=False)

    # 3. Soft-check by (title, year) when no unique identifier
    if not body.arxiv_id and not body.doi:
        soft = (
            supabase.table("papers")
            .select("id, title")
            .ilike("title", body.title)
            .eq("year", body.year)
            .limit(1)
            .execute()
        )
        if soft.data:
            logger.warning(
                "Soft-duplicate detected: title=%r year=%d — inserting anyway; "
                "existing paper_id=%s",
                body.title,
                body.year,
                soft.data[0]["id"],
            )

    # 4. Insert
    paper_row = {
        "title": body.title,
        "authors_json": body.authors_json,
        "year": body.year,
        "abstract_md": body.abstract_md,
        "arxiv_id": body.arxiv_id,
        "doi": body.doi,
        "external_url": body.external_url,
    }
    try:
        insert_resp = supabase.table("papers").insert(paper_row).execute()
    except Exception as exc:  # noqa: BLE001
        if not _is_unique_violation(exc):
            raise
        # Race: re-select whichever unique column was violated
        for field, value in [("arxiv_id", body.arxiv_id), ("doi", body.doi)]:
            if value:
                row = (
                    supabase.table("papers")
                    .select("id")
                    .eq(field, value)
                    .limit(1)
                    .execute()
                )
                if row.data:
                    return IngestPaperResponse(
                        paper_id=UUID(row.data[0]["id"]), created=False
                    )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="unique violation but re-select found nothing",
        ) from exc

    return IngestPaperResponse(
        paper_id=UUID(insert_resp.data[0]["id"]), created=True
    )
