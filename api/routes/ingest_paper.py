"""POST /admin/ingest-paper — thin wrapper around the shared dedup helper.

The core dedup-and-insert logic lives in paper_ingest_shared.ingest_paper so
that the user-facing /ingest-paper-user route can call the same code without
duplication.  No behaviour change for the operator.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from supabase import Client

from auth import require_internal_token
from paper_ingest_shared import ingest_paper as _ingest_paper
from schemas import IngestPaperRequest, IngestPaperResponse
from supabase_client import get_supabase_client

router = APIRouter()


@router.post(
    "/admin/ingest-paper",
    response_model=IngestPaperResponse,
    dependencies=[Depends(require_internal_token)],
)
def ingest_paper(
    body: IngestPaperRequest,
    supabase: Client = Depends(get_supabase_client),
) -> IngestPaperResponse:
    paper_id, created = _ingest_paper(
        supabase,
        title=body.title,
        authors_json=body.authors_json,
        year=body.year,
        abstract_md=body.abstract_md,
        arxiv_id=body.arxiv_id,
        doi=body.doi,
        external_url=body.external_url,
    )
    return IngestPaperResponse(paper_id=UUID(paper_id), created=created)
