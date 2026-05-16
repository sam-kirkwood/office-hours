from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from main import app
from supabase_client import get_supabase_client
from tests.fake_supabase import FakeSupabase

INTERNAL_TOKEN = "test-internal-token"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_TOKEN}"}

VALID_BODY = {
    "title": "Detection of Gravitational Waves",
    "authors_json": ["Abbott, B.", "Abbott, R."],
    "year": 2016,
    "abstract_md": "We report the first observation of gravitational waves.",
    "arxiv_id": "1602.03837",
    "doi": "10.1103/PhysRevLett.116.061102",
    "external_url": "https://arxiv.org/abs/1602.03837",
}


@pytest.fixture
def fake_supabase() -> FakeSupabase:
    fs = FakeSupabase()
    app.dependency_overrides[get_supabase_client] = lambda: fs
    try:
        yield fs
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(fake_supabase) -> TestClient:  # noqa: ARG001
    return TestClient(app)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_missing_bearer_returns_401(client: TestClient) -> None:
    response = client.post("/admin/ingest-paper", json=VALID_BODY)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_inserts_paper(client: TestClient, fake_supabase: FakeSupabase) -> None:
    new_id = str(uuid4())
    # no dedup hits
    fake_supabase.respond("papers", "select", lambda _: [])
    fake_supabase.respond("papers", "insert", lambda _: [{"id": new_id}])

    resp = client.post("/admin/ingest-paper", json=VALID_BODY, headers=AUTH_HEADERS)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["paper_id"] == new_id
    assert data["created"] is True

    inserts = [c for c in fake_supabase.calls if c.table == "papers" and c.op == "insert"]
    assert len(inserts) == 1
    row = inserts[0].payload
    assert row["title"] == VALID_BODY["title"]
    assert row["arxiv_id"] == VALID_BODY["arxiv_id"]


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_arxiv_dedup_returns_existing(client: TestClient, fake_supabase: FakeSupabase) -> None:
    existing_id = str(uuid4())
    fake_supabase.respond("papers", "select", lambda _: [{"id": existing_id}])

    resp = client.post("/admin/ingest-paper", json=VALID_BODY, headers=AUTH_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == existing_id
    assert data["created"] is False
    # no insert should have been attempted
    assert not any(c.table == "papers" and c.op == "insert" for c in fake_supabase.calls)


def test_doi_dedup_returns_existing(client: TestClient, fake_supabase: FakeSupabase) -> None:
    existing_id = str(uuid4())
    # arxiv_id absent → route skips arxiv select; first select is for doi
    body = {**VALID_BODY, "arxiv_id": None}
    fake_supabase.respond("papers", "select", lambda _: [{"id": existing_id}])

    resp = client.post("/admin/ingest-paper", json=body, headers=AUTH_HEADERS)

    assert resp.status_code == 200
    data = resp.json()
    assert data["paper_id"] == existing_id
    assert data["created"] is False
    assert not any(c.table == "papers" and c.op == "insert" for c in fake_supabase.calls)


def test_no_identifiers_inserts_with_warning(
    client: TestClient, fake_supabase: FakeSupabase
) -> None:
    """When neither arxiv_id nor doi is given, a soft-check is done but insert proceeds."""
    new_id = str(uuid4())
    body = {**VALID_BODY, "arxiv_id": None, "doi": None, "external_url": None}
    fake_supabase.respond("papers", "select", lambda _: [])
    fake_supabase.respond("papers", "insert", lambda _: [{"id": new_id}])

    resp = client.post("/admin/ingest-paper", json=body, headers=AUTH_HEADERS)

    assert resp.status_code == 200
    assert resp.json()["created"] is True
