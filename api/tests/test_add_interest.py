"""Tests for the add-interest dialog endpoints.

Covers the happy paths and the contract the next UI session depends on:
  - /parse: auth, single-segment specific, single-segment ambiguous.
  - /resolve: auth, link-to-existing path, generate-new path with concept tour.

Full edge-case coverage (slug-collision races, title collision into existing
node, hallucinated dedup slugs, multi-interest splitting) will be added when
the UI sessions wire the dialog up — see docs/phase-plans/phase-10-rev-plan.md.
"""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from anthropic_client import get_anthropic_client
from main import app
from prompts import add_interest as prompts
from supabase_client import get_supabase_client
from tests.fake_anthropic import FakeAnthropic
from tests.fake_supabase import FakeSupabase

INTERNAL_TOKEN = "test-internal-token"
AUTH_HEADERS = {"Authorization": f"Bearer {INTERNAL_TOKEN}"}

CALCULUS_ID = str(uuid4())
LINALG_ID = str(uuid4())
CALCULUS_NODE = {
    "id": CALCULUS_ID,
    "slug": "calculus-1",
    "title": "Calculus 1",
    "kind": "foundation",
    "description_md": "Limits, derivatives, integrals.",
    "subtopics_json": [
        "Rules for differentiation",
        "Integration techniques",
        "Sequences and series",
    ],
}
LINALG_NODE = {
    "id": LINALG_ID,
    "slug": "linear-algebra",
    "title": "Linear Algebra",
    "kind": "foundation",
    "description_md": "Vectors, matrices, eigenstructure.",
    "subtopics_json": [
        {"slug": "matrix-multiplication", "title": "Matrix multiplication"},
        {"slug": "eigenvalues", "title": "Eigenvalues and eigenvectors"},
    ],
}


@pytest.fixture
def fakes() -> tuple[FakeSupabase, FakeAnthropic]:
    fake_supabase = FakeSupabase()
    fake_anthropic = FakeAnthropic()
    app.dependency_overrides[get_supabase_client] = lambda: fake_supabase
    app.dependency_overrides[get_anthropic_client] = lambda: fake_anthropic
    try:
        yield fake_supabase, fake_anthropic
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(fakes) -> TestClient:  # noqa: ARG001
    return TestClient(app)


def _prime_llm_calls(supabase: FakeSupabase) -> None:
    supabase.respond("llm_calls", "insert", lambda _: [{"id": str(uuid4())}])


# ---------------------------------------------------------------------------
# /add-interest/parse
# ---------------------------------------------------------------------------


def test_parse_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/add-interest/parse",
        json={"user_id": str(uuid4()), "raw_text": "hi", "added_via": "survey"},
    )
    assert resp.status_code == 401


def test_parse_system_prompt_classifies_denial_of_mastery_as_teach() -> None:
    """Step 9c-i: explicit denial of mastery + want-to-learn language should
    route to 'teach', not 'consolidate'. The rule lives in the parser system
    prompt; this guards it against regression. Maya's verbatim input ('I want
    to actually understand bifurcations and attractors instead of just dropping
    the words') is the motivating case."""
    # Collapse the prompt's line-continuation whitespace so substring checks
    # don't depend on the source indentation.
    normalized = " ".join(prompts.build_parse_system_prompt().lower().split())
    # The rule names the teach mapping explicitly.
    assert "i want to actually understand" in normalized
    assert "all teach" in normalized
    # And it scopes consolidate away from denial-of-mastery phrasing.
    assert "consolidate is reserved for users who assert existing mastery" in normalized


def test_parse_specific_segment_returns_mirror_back_and_followup(
    client: TestClient, fakes
) -> None:
    supabase, anthropic = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    anthropic.queue(
        json.dumps(
            {
                "segments": [
                    {
                        "raw_text_segment": "I want my calculus back",
                        "specificity": "specific",
                        "implicit_intent": "refresh",
                        "mirror_back_md": "Got it — refreshing calculus.",
                        "optional_followup_md": "Want to tell me more?",
                        "path_options": [],
                        "dedup": {
                            "verdict": "same",
                            "matched_node_slug": "calculus-1",
                        },
                        "draft_intent_context": "refresh calculus foundations",
                    }
                ]
            }
        )
    )

    resp = client.post(
        "/add-interest/parse",
        json={
            "user_id": str(uuid4()),
            "raw_text": "I want my calculus back",
            "added_via": "survey",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["segments"]) == 1
    seg = body["segments"][0]
    assert seg["specificity"] == "specific"
    assert seg["implicit_intent"] == "refresh"
    assert seg["optional_followup_md"] == "Want to tell me more?"
    assert seg["path_options"] == []
    assert seg["dedup"]["verdict"] == "same"
    assert seg["dedup"]["matched_node_slug"] == "calculus-1"
    assert seg["draft_intent_context"] == "refresh calculus foundations"

    # Haiku call pinned to temperature=0 (classification).
    assert len(anthropic.messages.calls) == 1
    assert anthropic.messages.calls[0].get("temperature") == 0


def test_parse_ambiguous_segment_returns_path_options(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    anthropic.queue(
        json.dumps(
            {
                "segments": [
                    {
                        "raw_text_segment": "I want to learn semiconductors",
                        "specificity": "ambiguous",
                        "implicit_intent": "teach",
                        "mirror_back_md": "That covers a few angles — which sounds closest?",
                        "optional_followup_md": None,
                        "path_options": [
                            {
                                "key": "transistors-and-circuits",
                                "label_md": "How transistors and circuits actually work",
                                "draft_intent_context": "devices-and-circuits angle, teach intent",
                                "what_you_learn": "How p-n junctions and transistors behave.",
                                "endpoint": "I can analyse a transistor amplifier.",
                                "math_intensity": "algebra",
                                "mode_lean": "problems",
                                "leans_on_prereq_slugs": [],
                            },
                            {
                                "key": "deeper-physics",
                                "label_md": "The deeper physics of why semiconductors behave this way",
                                "draft_intent_context": "solid-state-physics angle, teach intent",
                                "what_you_learn": "Band theory and Fermi levels.",
                                "endpoint": "I can explain doping in QM terms.",
                                "math_intensity": "linear_algebra",
                                "mode_lean": "balanced",
                                "leans_on_prereq_slugs": [],
                            },
                        ],
                        "dedup": {"verdict": "new", "matched_node_slug": None},
                        "draft_intent_context": "semiconductors, teach intent",
                    }
                ]
            }
        )
    )

    resp = client.post(
        "/add-interest/parse",
        json={
            "user_id": str(uuid4()),
            "raw_text": "I want to learn semiconductors",
            "added_via": "survey",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    seg = resp.json()["segments"][0]
    assert seg["specificity"] == "ambiguous"
    assert seg["optional_followup_md"] is None
    assert len(seg["path_options"]) == 2
    assert seg["path_options"][0]["key"] == "transistors-and-circuits"
    assert seg["dedup"]["verdict"] == "new"
    assert seg["dedup"]["matched_node_slug"] is None


def test_parse_drops_hallucinated_dedup_slug(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    anthropic.queue(
        json.dumps(
            {
                "segments": [
                    {
                        "raw_text_segment": "foo",
                        "specificity": "specific",
                        "implicit_intent": "teach",
                        "mirror_back_md": "...",
                        "optional_followup_md": "Want to tell me more?",
                        "path_options": [],
                        "dedup": {
                            "verdict": "same",
                            "matched_node_slug": "does-not-exist",
                        },
                        "draft_intent_context": "...",
                    }
                ]
            }
        )
    )

    resp = client.post(
        "/add-interest/parse",
        json={"user_id": str(uuid4()), "raw_text": "foo", "added_via": "survey"},
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    seg = resp.json()["segments"][0]
    assert seg["dedup"]["verdict"] == "new"
    assert seg["dedup"]["matched_node_slug"] is None


# ---------------------------------------------------------------------------
# /add-interest/resolve
# ---------------------------------------------------------------------------


def test_resolve_missing_bearer_returns_401(client: TestClient) -> None:
    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "x",
            "final_intent_text": "x",
            "intent_context": "x",
        },
    )
    assert resp.status_code == 401


def test_resolve_existing_slug_links_without_sonnet(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    ui_id = str(uuid4())

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    # Concept tour: prereq edges for the linked node — none in this minimal fixture.
    supabase.respond("edges", "select", lambda _: [])
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "I want my calculus back",
            "final_intent_text": "Refresh calculus foundations",
            "intent_context": "refresh calculus foundations",
            "existing_node_slug": "calculus-1",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user_interest_id"] == ui_id
    assert body["node_id"] == CALCULUS_ID
    assert body["node_slug"] == "calculus-1"
    assert body["verdict"] == "same"
    assert body["intent_context"] == "refresh calculus foundations"
    assert body["starter_preview_md"].startswith("Your first item will be:")

    # No Anthropic calls — link path skips Sonnet.
    assert anthropic.messages.calls == []

    # user_interests insert carries intent_context.
    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert len(ui_inserts) == 1
    payload = ui_inserts[0].payload
    assert payload["node_id"] == CALCULUS_ID
    assert payload["intent_context"] == "refresh calculus foundations"
    assert payload["added_via"] == "survey"


def test_resolve_unknown_existing_slug_returns_400(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "x",
            "final_intent_text": "x",
            "intent_context": "x",
            "existing_node_slug": "no-such-node",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400


def test_resolve_new_node_writes_intent_context_and_tour(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    ui_id = str(uuid4())

    supabase.respond(
        "nodes",
        "select",
        lambda _: [CALCULUS_NODE, LINALG_NODE],
    )
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond(
        "edges",
        "select",
        lambda _: [
            {
                "source_node_id": CALCULUS_ID,
                "edge_kind": "prerequisite",
                "target_node_id": new_node_id,
            },
            {
                "source_node_id": LINALG_ID,
                "edge_kind": "prerequisite",
                "target_node_id": new_node_id,
            },
        ],
    )
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    anthropic.queue(
        json.dumps(
            {
                "title": "Kalman Filters",
                "slug": "kalman-filters",
                "description_md": "Recursive state estimators.",
                "domain": "applied",
                "difficulty_hint": "core",
                "subtopics": [
                    "Linear-Gaussian model",
                    "Kalman gain",
                    "Extended Kalman filter",
                ],
                "proposed_prerequisite_slugs": ["calculus-1", "linear-algebra"],
                "entry_point_preview_md": (
                    "a conceptual entrance to recursive state estimation"
                ),
            }
        )
    )

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "explicit_request",
            "raw_text": "I want to learn Kalman filters",
            "final_intent_text": "Learn Kalman filters for state estimation",
            "intent_context": "applied-engineering angle, teach intent",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["node_id"] == new_node_id
    assert body["node_slug"] == "kalman-filters"
    assert body["verdict"] == "new"
    assert body["intent_context"] == "applied-engineering angle, teach intent"
    assert "recursive state estimation" in body["starter_preview_md"]

    # Sonnet called once.
    assert len(anthropic.messages.calls) == 1

    # Node was inserted with kind='interest' and the generated payload.
    node_inserts = [c for c in supabase.calls if c.table == "nodes" and c.op == "insert"]
    assert len(node_inserts) == 1
    assert node_inserts[0].payload["slug"] == "kalman-filters"
    assert node_inserts[0].payload["kind"] == "interest"

    # Prerequisite edges inserted per-row: calculus-1 → new, linear-algebra → new.
    edge_inserts = [c for c in supabase.calls if c.table == "edges" and c.op == "insert"]
    assert len(edge_inserts) == 2
    edges = [c.payload for c in edge_inserts]
    assert {e["source_node_id"] for e in edges} == {CALCULUS_ID, LINALG_ID}
    assert all(e["edge_kind"] == "prerequisite" for e in edges)

    # user_interests row carries intent_context.
    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert len(ui_inserts) == 1
    assert ui_inserts[0].payload["intent_context"] == "applied-engineering angle, teach intent"
    assert ui_inserts[0].payload["added_via"] == "explicit_request"

    # Node-readiness pass (Phase 13 Step 3): node-level tiles, one per prereq
    # node, NOT per subtopic. No path_json → edges fallback over both prereqs.
    readiness = body["node_readiness"]
    titles = {t["node_title"] for t in readiness}
    assert "Calculus 1" in titles
    assert "Linear Algebra" in titles
    calc_tile = next(t for t in readiness if t["node_title"] == "Calculus 1")
    assert calc_tile["node_slug"] == "calculus-1"
    # Description preview is the leading slice of description_md.
    assert calc_tile["node_description_preview"].startswith("Limits, derivatives")


def test_node_readiness_includes_topical_prereqs(client: TestClient, fakes) -> None:
    """Phase 13 Step 3 (§B1/§B3): the node-readiness pass includes ALL prereq
    KINDS — foundation AND interest (topical, e.g. SR/GR). The old subtopic
    _concept_tour deprioritised interest-kind prereqs to a fallback; the
    explicit fix here is that a topical prereq like Special Relativity must
    appear in the readiness pass for things like astrophysics.

    No path_json → edges fallback over the node's actual prereq edges, all
    kinds included."""
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    calc_id = CALCULUS_ID
    sr_id = str(uuid4())

    sr_node = {
        "id": sr_id,
        "slug": "special-relativity",
        "title": "Special Relativity",
        "kind": "interest",  # topical prereq — NOT a foundation
        "description_md": "Lorentz transformations and spacetime.",
        "subtopics_json": ["Lorentz transformations", "Four-vectors"],
    }

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE, sr_node])
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond(
        "edges",
        "select",
        lambda _: [
            {"source_node_id": calc_id, "edge_kind": "prerequisite", "target_node_id": new_node_id},
            {"source_node_id": sr_id, "edge_kind": "prerequisite", "target_node_id": new_node_id},
        ],
    )
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": str(uuid4())}])

    anthropic.queue(
        json.dumps(
            {
                "title": "Astrophysics",
                "slug": "astrophysics",
                "description_md": "Stars, galaxies, cosmology.",
                "domain": "physics",
                "difficulty_hint": "core",
                "subtopics": ["Stellar structure", "Cosmology"],
                "proposed_prerequisite_slugs": ["calculus-1", "special-relativity"],
                "entry_point_preview_md": "an entrance to astrophysics",
            }
        )
    )

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "astrophysics",
            "final_intent_text": "Learn astrophysics",
            "intent_context": "teach intent",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    readiness = resp.json()["node_readiness"]
    titles = {t["node_title"] for t in readiness}
    # The interest-kind topical prereq (SR) must be present, not dropped.
    assert "Special Relativity" in titles
    assert "Calculus 1" in titles


def test_node_readiness_uses_leans_on_prereq_slugs(client: TestClient, fakes) -> None:
    """Phase 13 Step 3 (resolved decision 2): when the user picked a path,
    path_json.leans_on_prereq_slugs scopes the readiness pass — the curator
    reads the path's soft prereq emphasis as a structured field. SR (a topical
    prereq named in leans_on) must appear even though it's interest-kind."""
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    sr_id = str(uuid4())

    sr_node = {
        "id": sr_id,
        "slug": "special-relativity",
        "title": "Special Relativity",
        "kind": "interest",
        "description_md": "Lorentz transformations and spacetime.",
        "subtopics_json": ["Lorentz transformations"],
    }
    # GR exists but is NOT in leans_on — it must be excluded.
    gr_node = {
        "id": str(uuid4()),
        "slug": "general-relativity",
        "title": "General Relativity",
        "kind": "interest",
        "description_md": "Curved spacetime.",
        "subtopics_json": ["Geodesics"],
    }

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE, sr_node, gr_node])
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    # An edges responder would return MORE prereqs, but leans_on must take
    # precedence — the readiness pass must NOT consult edges when leans_on set.
    supabase.respond("edges", "select", lambda _: [
        {"source_node_id": gr_node["id"], "edge_kind": "prerequisite", "target_node_id": new_node_id},
    ])
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": str(uuid4())}])

    anthropic.queue(
        json.dumps(
            {
                "title": "Astrophysics",
                "slug": "astrophysics",
                "description_md": "Stars, galaxies.",
                "domain": "physics",
                "difficulty_hint": "core",
                "subtopics": ["Stellar structure"],
                "proposed_prerequisite_slugs": ["calculus-1"],
                "entry_point_preview_md": "an entrance",
            }
        )
    )

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "astrophysics, the research-following angle",
            "final_intent_text": "Follow astrophysics research",
            "intent_context": "research-following angle",
            "path_json": {
                "leans_on_prereq_slugs": ["calculus-1", "special-relativity"],
                "mode_lean": "papers",
            },
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    readiness = resp.json()["node_readiness"]
    titles = {t["node_title"] for t in readiness}
    assert "Special Relativity" in titles   # named in leans_on
    assert "Calculus 1" in titles           # named in leans_on
    assert "General Relativity" not in titles  # NOT in leans_on → excluded


def test_node_readiness_submit_writes_node_level_states(
    client: TestClient, fakes
) -> None:
    """POST /add-interest/node-readiness maps solid/rusty/new to
    comfortable/active/unseen and upserts node-level user_node_states."""
    supabase, _ = fakes
    supabase.respond("user_node_states", "upsert", lambda _: [{}])

    user_id = str(uuid4())
    n_solid = str(uuid4())
    n_rusty = str(uuid4())
    n_new = str(uuid4())

    resp = client.post(
        "/add-interest/node-readiness",
        json={
            "user_id": user_id,
            "user_interest_id": str(uuid4()),
            "node_states": [
                {"node_id": n_solid, "state": "solid"},
                {"node_id": n_rusty, "state": "rusty"},
                {"node_id": n_new, "state": "new"},
            ],
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["written"] == 3

    upserts = [
        c for c in supabase.calls
        if c.table == "user_node_states" and c.op == "upsert"
    ]
    assert len(upserts) == 3
    by_node = {c.payload["node_id"]: c.payload["state"] for c in upserts}
    assert by_node[n_solid] == "comfortable"
    assert by_node[n_rusty] == "active"
    assert by_node[n_new] == "unseen"
    # All writes carry the user_id.
    assert all(c.payload["user_id"] == user_id for c in upserts)


def test_resolve_related_slug_writes_related_edge(client: TestClient, fakes) -> None:
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    ui_id = str(uuid4())

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond("edges", "select", lambda _: [])  # empty prereqs → empty tour
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    anthropic.queue(
        json.dumps(
            {
                "title": "Fourier Analysis",
                "slug": "fourier-analysis",
                "description_md": "Decomposing functions into sinusoids.",
                "domain": "math",
                "difficulty_hint": "core",
                "subtopics": ["Fourier series", "Fourier transform"],
                "proposed_prerequisite_slugs": [],
                "entry_point_preview_md": "a conceptual entrance to Fourier methods",
            }
        )
    )

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "fourier",
            "final_intent_text": "Learn Fourier analysis",
            "intent_context": "math angle, teach intent",
            "related_node_slug": "calculus-1",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["verdict"] == "related"

    edge_inserts = [c for c in supabase.calls if c.table == "edges" and c.op == "insert"]
    assert len(edge_inserts) == 1
    edges = [c.payload for c in edge_inserts]
    assert any(
        e["source_node_id"] == CALCULUS_ID
        and e["target_node_id"] == new_node_id
        and e["edge_kind"] == "related"
        for e in edges
    )


def test_resolve_writes_edges_when_related_slug_overlaps_prereqs(
    client: TestClient, fakes
) -> None:
    """Regression for the orphaned-node bug: when the resolved related_slug also
    appears in Sonnet's proposed_prerequisite_slugs, the two edge rows collide on
    the (source, target) uniqueness constraint. A batched insert rolled the whole
    batch back, leaving the node with no edges. Per-row inserts must keep the
    surviving edge instead of dropping both."""
    supabase, anthropic = fakes
    new_node_id = str(uuid4())
    ui_id = str(uuid4())

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "select", lambda _: [])
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    # Simulate the DB uniqueness constraint: the prerequisite edge inserts
    # cleanly, but the duplicate (source, target) 'related' edge raises 23505.
    def edges_insert(call):
        if call.payload.get("edge_kind") == "related":
            return Exception("duplicate key value violates unique constraint (23505)")
        return []

    supabase.respond("edges", "insert", edges_insert)

    anthropic.queue(
        json.dumps(
            {
                "title": "Fourier Analysis",
                "slug": "fourier-analysis",
                "description_md": "Decomposing functions into sinusoids.",
                "domain": "math",
                "difficulty_hint": "core",
                "subtopics": ["Fourier series", "Fourier transform"],
                # Sonnet redundantly lists the related slug as a prerequisite too.
                "proposed_prerequisite_slugs": ["calculus-1"],
                "entry_point_preview_md": "a conceptual entrance to Fourier methods",
            }
        )
    )

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "fourier",
            "final_intent_text": "Learn Fourier analysis",
            "intent_context": "math angle, teach intent",
            "related_node_slug": "calculus-1",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["verdict"] == "related"

    # Both rows were attempted per-row; the prerequisite survived even though
    # the related edge collided. The batch was NOT rolled back wholesale.
    edge_inserts = [c for c in supabase.calls if c.table == "edges" and c.op == "insert"]
    assert len(edge_inserts) == 2
    kinds = [c.payload["edge_kind"] for c in edge_inserts]
    assert "prerequisite" in kinds
    assert "related" in kinds


def test_resolve_rejects_both_existing_and_related(client: TestClient, fakes) -> None:
    supabase, _ = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "survey",
            "raw_text": "x",
            "final_intent_text": "x",
            "intent_context": "x",
            "existing_node_slug": "calculus-1",
            "related_node_slug": "calculus-1",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Phase 13 Step 2 — rich paths + path_json
# ---------------------------------------------------------------------------

_RICH_PATH_OPTION = {
    "key": "transistors-and-circuits",
    "label_md": "How transistors and circuits actually work",
    "draft_intent_context": "Curious about how transistors and circuits work, device-physics angle.",
    "what_you_learn": "How p-n junctions, diodes, and bipolar/FET transistors behave; how to read a datasheet.",
    "endpoint": "I can analyse a simple transistor amplifier and design a basic circuit.",
    "math_intensity": "algebra",
    "mode_lean": "problems",
    "leans_on_prereq_slugs": ["calculus-1"],
}

_RICH_PATH_OPTION_2 = {
    "key": "deeper-physics",
    "label_md": "The deeper physics of why semiconductors behave this way",
    "draft_intent_context": "Wants to understand band structure and QM of semiconductors.",
    "what_you_learn": "Band theory, Fermi levels, effective mass, direct vs indirect band gaps.",
    "endpoint": "I can explain why silicon conducts under doping in terms of quantum mechanics.",
    "math_intensity": "linear_algebra",
    "mode_lean": "balanced",
    "leans_on_prereq_slugs": ["calculus-1", "linear-algebra"],
}


def test_parse_ambiguous_segment_rich_fields(client: TestClient, fakes) -> None:
    """Rich path fields are present on ambiguous segment path_options."""
    supabase, anthropic = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE, LINALG_NODE])
    _prime_llm_calls(supabase)

    anthropic.queue(
        json.dumps(
            {
                "segments": [
                    {
                        "raw_text_segment": "I want to learn semiconductors",
                        "specificity": "ambiguous",
                        "implicit_intent": "teach",
                        "mirror_back_md": "That covers a few angles — which sounds closest?",
                        "optional_followup_md": None,
                        "path_options": [_RICH_PATH_OPTION, _RICH_PATH_OPTION_2],
                        "dedup": {"verdict": "new", "matched_node_slug": None},
                        "draft_intent_context": "semiconductors, teach intent",
                    }
                ]
            }
        )
    )

    resp = client.post(
        "/add-interest/parse",
        json={
            "user_id": str(uuid4()),
            "raw_text": "I want to learn semiconductors",
            "added_via": "survey",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    opts = resp.json()["segments"][0]["path_options"]
    assert len(opts) == 2
    opt = opts[0]
    assert opt["key"] == "transistors-and-circuits"
    assert "what_you_learn" in opt
    assert "datasheet" in opt["what_you_learn"]
    assert "endpoint" in opt
    assert opt["endpoint"].startswith("I can")
    assert opt["math_intensity"] == "algebra"
    assert opt["mode_lean"] == "problems"
    assert opt["leans_on_prereq_slugs"] == ["calculus-1"]

    opt2 = opts[1]
    assert opt2["math_intensity"] == "linear_algebra"
    assert set(opt2["leans_on_prereq_slugs"]) == {"calculus-1", "linear-algebra"}


def test_parse_drops_hallucinated_leans_on_slugs(client: TestClient, fakes) -> None:
    """Unknown slugs in leans_on_prereq_slugs are silently dropped."""
    supabase, anthropic = fakes
    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    _prime_llm_calls(supabase)

    bad_path = {
        **_RICH_PATH_OPTION,
        "leans_on_prereq_slugs": ["calculus-1", "does-not-exist"],
    }
    anthropic.queue(
        json.dumps(
            {
                "segments": [
                    {
                        "raw_text_segment": "I want to learn semiconductors",
                        "specificity": "ambiguous",
                        "implicit_intent": "teach",
                        "mirror_back_md": "Which angle?",
                        "optional_followup_md": None,
                        "path_options": [bad_path],
                        "dedup": {"verdict": "new", "matched_node_slug": None},
                        "draft_intent_context": "semiconductors, teach intent",
                    }
                ]
            }
        )
    )

    resp = client.post(
        "/add-interest/parse",
        json={
            "user_id": str(uuid4()),
            "raw_text": "I want to learn semiconductors",
            "added_via": "survey",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text
    slugs = resp.json()["segments"][0]["path_options"][0]["leans_on_prereq_slugs"]
    assert slugs == ["calculus-1"]
    assert "does-not-exist" not in slugs


def test_resolve_persists_path_json(client: TestClient, fakes) -> None:
    """path_json passed to resolve is written to the user_interests row."""
    supabase, anthropic = fakes
    ui_id = str(uuid4())
    new_node_id = str(uuid4())

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond("edges", "select", lambda _: [])
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    anthropic.queue(
        json.dumps(
            {
                "title": "Semiconductors — Devices",
                "slug": "semiconductors-devices",
                "description_md": "How transistors work.",
                "domain": "physics",
                "difficulty_hint": "core",
                "subtopics": ["p-n junction", "transistors"],
                "proposed_prerequisite_slugs": [],
                "entry_point_preview_md": "a conceptual entrance to semiconductor devices",
            }
        )
    )

    path_json_sent = {
        "key": "transistors-and-circuits",
        "label_md": "How transistors and circuits actually work",
        "what_you_learn": "How p-n junctions and transistors behave.",
        "endpoint": "I can analyse a transistor amplifier.",
        "math_intensity": "algebra",
        "mode_lean": "problems",
        "leans_on_prereq_slugs": ["calculus-1"],
    }

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "explicit_request",
            "raw_text": "semiconductors",
            "final_intent_text": "Semiconductors — transistors and circuits",
            "intent_context": "Device-physics angle, how transistors work.",
            "path_json": path_json_sent,
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text

    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert len(ui_inserts) == 1
    written_path = ui_inserts[0].payload["path_json"]
    assert written_path is not None
    assert written_path["key"] == "transistors-and-circuits"
    assert written_path["mode_lean"] == "problems"
    assert written_path["leans_on_prereq_slugs"] == ["calculus-1"]


def test_resolve_path_json_leans_on_validated(client: TestClient, fakes) -> None:
    """Unknown leans_on slugs in path_json are dropped before the DB write."""
    supabase, anthropic = fakes
    ui_id = str(uuid4())
    new_node_id = str(uuid4())

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond("edges", "select", lambda _: [])
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    anthropic.queue(
        json.dumps(
            {
                "title": "Semiconductors — Devices",
                "slug": "semiconductors-devices-v2",
                "description_md": "How transistors work.",
                "domain": "physics",
                "difficulty_hint": "core",
                "subtopics": ["p-n junction", "transistors"],
                "proposed_prerequisite_slugs": [],
                "entry_point_preview_md": "a conceptual entrance to semiconductor devices",
            }
        )
    )

    path_json_with_bad_slug = {
        "key": "transistors-and-circuits",
        "label_md": "How transistors work",
        "what_you_learn": "How p-n junctions work.",
        "endpoint": "I can analyse a circuit.",
        "math_intensity": "algebra",
        "mode_lean": "problems",
        "leans_on_prereq_slugs": ["calculus-1", "hallucinated-slug"],
    }

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "explicit_request",
            "raw_text": "semiconductors",
            "final_intent_text": "Semiconductors — transistors",
            "intent_context": "Device-physics angle.",
            "path_json": path_json_with_bad_slug,
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text

    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert len(ui_inserts) == 1
    written_slugs = ui_inserts[0].payload["path_json"]["leans_on_prereq_slugs"]
    assert written_slugs == ["calculus-1"]
    assert "hallucinated-slug" not in written_slugs


# ---------------------------------------------------------------------------
# Phase 13 Step 3 — altitude + entry-lane
# ---------------------------------------------------------------------------


def test_altitude_stored_on_resolve(client: TestClient, fakes) -> None:
    """altitude passed to /resolve is written to the user_interests row as a
    structured field."""
    supabase, anthropic = fakes
    ui_id = str(uuid4())
    new_node_id = str(uuid4())

    supabase.respond("nodes", "select", lambda _: [CALCULUS_NODE])
    supabase.respond("nodes", "insert", lambda _: [{"id": new_node_id}])
    supabase.respond("edges", "insert", lambda _: [])
    supabase.respond("edges", "select", lambda _: [])
    _prime_llm_calls(supabase)
    supabase.respond("user_interests", "insert", lambda _: [{"id": ui_id}])

    anthropic.queue(
        json.dumps(
            {
                "title": "Quantum Field Theory",
                "slug": "quantum-field-theory",
                "description_md": "Fields, particles, and interactions.",
                "domain": "physics",
                "difficulty_hint": "advanced",
                "subtopics": ["Lagrangians", "Feynman diagrams"],
                "proposed_prerequisite_slugs": [],
                "entry_point_preview_md": "a consolidation problem on QFT",
            }
        )
    )

    resp = client.post(
        "/add-interest/resolve",
        json={
            "user_id": str(uuid4()),
            "added_via": "explicit_request",
            "raw_text": "QFT — I know this well, want to go deep",
            "final_intent_text": "Quantum field theory, advanced",
            "intent_context": "go-deep angle",
            "altitude": "go_deep",
        },
        headers=AUTH_HEADERS,
    )
    assert resp.status_code == 200, resp.text

    ui_inserts = [c for c in supabase.calls if c.table == "user_interests" and c.op == "insert"]
    assert len(ui_inserts) == 1
    assert ui_inserts[0].payload["altitude"] == "go_deep"


def _ui_responder(*, intent_context: str | None, altitude: str | None):
    """FakeSupabase responder for a single user_interests row."""
    def responder(_call):
        return [{"intent_context": intent_context, "altitude": altitude}]
    return responder


def test_derive_intent_altitude_go_deep() -> None:
    """altitude='go_deep' → consolidate, read as a structured field (no prose)."""
    from curator_inputs import derive_intent

    fake = FakeSupabase()
    fake.respond("user_interests", "select", _ui_responder(intent_context=None, altitude="go_deep"))
    assert derive_intent(fake, user_id="u", node_id="n") == "consolidate"


def test_derive_intent_altitude_coming_back() -> None:
    """altitude='coming_back' → refresh."""
    from curator_inputs import derive_intent

    fake = FakeSupabase()
    fake.respond("user_interests", "select", _ui_responder(intent_context=None, altitude="coming_back"))
    assert derive_intent(fake, user_id="u", node_id="n") == "refresh"


def test_derive_intent_altitude_new() -> None:
    """altitude='new' (no intent_context) → teach."""
    from curator_inputs import derive_intent

    fake = FakeSupabase()
    fake.respond("user_interests", "select", _ui_responder(intent_context=None, altitude="new"))
    assert derive_intent(fake, user_id="u", node_id="n") == "teach"


def test_derive_intent_altitude_overrides_prose() -> None:
    """altitude='go_deep' wins even when intent_context prose says 'rusty'
    (structured field takes precedence — the carry-forward discipline)."""
    from curator_inputs import derive_intent

    fake = FakeSupabase()
    fake.respond(
        "user_interests", "select",
        _ui_responder(intent_context="rusty on ODEs, want a refresh", altitude="go_deep"),
    )
    assert derive_intent(fake, user_id="u", node_id="n") == "consolidate"


def test_derive_intent_altitude_none_falls_back_to_prose() -> None:
    """altitude=None → fall back to intent_context prose keyword matching."""
    from curator_inputs import derive_intent

    fake = FakeSupabase()
    fake.respond(
        "user_interests", "select",
        _ui_responder(intent_context="rusty on ODEs, want a refresh", altitude=None),
    )
    assert derive_intent(fake, user_id="u", node_id="n") == "refresh"


def test_derive_entry_lane_go_deep_skips_entrance() -> None:
    """altitude='go_deep' → lane 3 (skip entrance), without consulting history."""
    from curator_inputs import derive_entry_lane

    fake = FakeSupabase()
    fake.respond(
        "user_interests", "select",
        lambda _call: [{"altitude": "go_deep"}],
    )
    assert derive_entry_lane(fake, user_id="u", topic_node_id="n") == 3


def test_derive_entry_lane_coming_back() -> None:
    """altitude='coming_back' → lane 2 (light-recall entrance)."""
    from curator_inputs import derive_entry_lane

    fake = FakeSupabase()
    fake.respond(
        "user_interests", "select",
        lambda _call: [{"altitude": "coming_back"}],
    )
    assert derive_entry_lane(fake, user_id="u", topic_node_id="n") == 2


def test_derive_entry_lane_new_entry_point_gets_lane_1() -> None:
    """altitude='new' + no prior attempts on topic → lane 1 (entrance)."""
    from curator_inputs import derive_entry_lane

    fake = FakeSupabase()
    fake.respond("user_interests", "select", lambda _call: [{"altitude": "new"}])
    # is_entry_point: no attempts → True → lane 1.
    fake.respond("attempts", "select", lambda _call: [])
    assert derive_entry_lane(fake, user_id="u", topic_node_id="n") == 1
