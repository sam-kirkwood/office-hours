"""Drive the persona walkthrough end-to-end.

Persona: Dr. Maya Chen — computational neuroscience postdoc bridging from
wet-lab systems neuro into theoretical modelling. See persona.md.

Run stages individually via CLI argument:
    uv run --project api python scripts/persona_walkthrough/walkthrough.py <stage>

Stages: stage1, stage2, stage3, stage4, stage5, stage6, stage7,
        cold_start, surface_daily, inspect
"""
from __future__ import annotations

import json
import os
import sys
import re
from pathlib import Path

import httpx
from supabase import create_client

# Windows console hates unicode arrows etc — force UTF-8 stdout.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

USER_ID = "4386f329-485a-40e4-b8a4-de57944c5e05"  # Maya — auth.users id
API_BASE = "http://localhost:8000"

# Credentials are sourced from api/.env (gitignored) — never check them in.
# Override via env var (SUPABASE_URL, SUPABASE_SECRET_KEY, INTERNAL_API_TOKEN).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _REPO_ROOT / "api" / ".env"


def _load_dotenv() -> dict:
    out = {}
    if _ENV_PATH.exists():
        for raw in _ENV_PATH.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            out[key.strip()] = val.strip().strip("'\"")
    return out


_env = _load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL") or _env.get("SUPABASE_URL", "")
SECRET = os.environ.get("SUPABASE_SECRET_KEY") or _env.get("SUPABASE_SECRET_KEY", "")
INTERNAL_TOKEN = os.environ.get("INTERNAL_API_TOKEN") or _env.get("INTERNAL_API_TOKEN", "")

if not (SUPABASE_URL and SECRET and INTERNAL_TOKEN):
    sys.exit(
        "Missing creds. Set SUPABASE_URL, SUPABASE_SECRET_KEY, INTERNAL_API_TOKEN "
        "in api/.env or as env vars."
    )


OUT_DIR = Path(__file__).parent / "out"
OUT_DIR.mkdir(exist_ok=True)


def sb():
    return create_client(SUPABASE_URL, SECRET)


def api_post(path: str, payload: dict, timeout: float = 120.0) -> dict:
    r = httpx.post(
        f"{API_BASE}{path}",
        json=payload,
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
        timeout=timeout,
    )
    if r.status_code >= 400:
        print(f"!! {path} → {r.status_code}")
        print(r.text[:1000])
        r.raise_for_status()
    return r.json()


def dump(name: str, obj) -> None:
    p = OUT_DIR / f"{name}.json"
    p.write_text(json.dumps(obj, indent=2, default=str))
    print(f"wrote {p}")


# ============================================================
# Stage 1 — Background survey row
# ============================================================
def stage1():
    client = sb()
    background = {
        "domains": [
            {
                "key": "mathematics",
                "subareas": ["linear-algebra", "odes-pdes", "probability-stats"],
                "relationship": "studied_reconnecting",
            },
            {
                "key": "computation",
                "subareas": ["machine-learning", "scientific-computing", "data-analysis"],
                "relationship": "encounter_at_work",
            },
            {
                "key": "biology",
                "subareas": ["neuroscience", "molecular-cell"],
                "relationship": "follow_field",
            },
        ]
    }
    free_text = (
        "Neuro postdoc moving toward computational theory. Linear algebra and ODEs "
        "are rusty; information theory and dynamical systems are gaps. I read neuro "
        "papers fluently but the math sections are where I get stuck."
    )

    # Upsert by user_id (one survey per user — RLS allows the service role through)
    existing = (
        client.table("surveys").select("id").eq("user_id", USER_ID).limit(1).execute()
    )
    row = {
        "user_id": USER_ID,
        "free_text_intent": free_text,
        "background_json": background,
        "completed_stages": ["stage1"],
        "node_ratings_json": {},
        "comfort_responses_json": {},
        "pending_interests_json": {},
        "mode_balance": 0.5,
    }
    if existing.data:
        client.table("surveys").update(row).eq("id", existing.data[0]["id"]).execute()
    else:
        client.table("surveys").insert(row).execute()

    survey = (
        client.table("surveys").select("*").eq("user_id", USER_ID).single().execute()
    )
    dump("stage1_survey", survey.data)
    print("OK — stage 1 written")


# ============================================================
# Stage 2 — Foundations
# ============================================================
def stage2():
    client = sb()
    # Maya marks: linear-algebra, odes, probability, statistics as 'refresh' → state='active'
    refresh_slugs = ["linear-algebra", "odes", "probability", "statistics"]
    nodes = (
        client.table("nodes")
        .select("id, slug, title")
        .in_("slug", refresh_slugs)
        .execute()
    )
    print("matched foundation nodes:", [(n["slug"], n["title"]) for n in nodes.data])

    state_rows = [
        {"user_id": USER_ID, "node_id": n["id"], "state": "active"}
        for n in nodes.data
    ]
    # upsert by (user_id, node_id)
    client.table("user_node_states").upsert(
        state_rows, on_conflict="user_id,node_id"
    ).execute()

    # also record node_ratings_json on the surveys row for parity with the UI
    ratings = {n["slug"]: "refresh" for n in nodes.data}
    client.table("surveys").update(
        {"node_ratings_json": ratings, "completed_stages": ["stage1", "stage2"]}
    ).eq("user_id", USER_ID).execute()

    dump("stage2_marked_nodes", [n["slug"] for n in nodes.data])
    print(f"OK — {len(nodes.data)} foundation nodes marked 'active'")


# ============================================================
# Stage 3 — Suggest interests
# ============================================================
def stage3():
    client = sb()
    # Build the call payload per schema
    marked = (
        client.table("user_node_states")
        .select("node_id")
        .eq("user_id", USER_ID)
        .eq("state", "active")
        .execute()
    )
    marked_ids = [r["node_id"] for r in marked.data]

    # Use the SAME domain labels surveyDomains.ts would resolve them to
    domains = [
        {
            "key": "mathematics",
            "label": "Mathematics",
            "subarea_labels": [
                "Linear algebra",
                "ODEs & PDEs",
                "Probability & stats",
            ],
            "relationship_label": "I studied this",
        },
        {
            "key": "computation",
            "label": "Computation",
            "subarea_labels": [
                "Machine learning",
                "Scientific computing",
                "Data analysis",
            ],
            "relationship_label": "I encounter this in my work",
        },
        {
            "key": "biology",
            "label": "Biology",
            "subarea_labels": ["Neuroscience", "Molecular & cell"],
            "relationship_label": "I follow this field",
        },
    ]

    payload = {
        "user_id": USER_ID,
        "domains": domains,
        "marked_foundation_node_ids": marked_ids,
    }
    resp = api_post("/survey/suggest-interests", payload, timeout=120.0)
    dump("stage3_suggestions", resp)
    print(f"OK — {len(resp['suggestions'])} suggestions returned")
    for s in resp["suggestions"]:
        print(f"  - {s['title']}: {s['why_suggested_md']}")


# ============================================================
# Stage 4 — Add-interest dialog (parse + resolve)
# ============================================================
def stage4():
    """Maya selects 2 suggestions (if good) + types her 2 free-text interests.

    For the walkthrough we use her *intent texts* — they may match suggested
    tiles or her free-text input. We funnel each through parse → resolve.
    """
    # Read suggestions for review
    suggestions = json.loads((OUT_DIR / "stage3_suggestions.json").read_text())
    print("Suggestions returned:")
    for s in suggestions["suggestions"]:
        print(f"  {s['slug']}: {s['title']}")

    # Maya's actual chosen interests — written as free-text statements
    # in her own voice. The parse call should dedupe these against the
    # megagraph; if a suggested tile matches one, great.
    raw_inputs = [
        "Information theory for neuroscience — entropy and mutual information "
        "for analysing spike trains.",
        "Dynamical systems for neural circuits — I want to actually understand "
        "bifurcations and attractors instead of just dropping the words.",
    ]

    parsed_segments = []
    for raw in raw_inputs:
        print(f"\n--- parsing: {raw[:60]}...")
        resp = api_post(
            "/add-interest/parse",
            {"user_id": USER_ID, "raw_text": raw, "added_via": "survey"},
            timeout=120.0,
        )
        parsed_segments.append({"raw_text": raw, "response": resp})
        for seg in resp["segments"]:
            print(f"  mirror: {seg['mirror_back_md']}")
            print(f"  dedup: {seg['dedup']}, intent={seg['implicit_intent']}, "
                  f"specificity={seg['specificity']}")
            if seg.get("optional_followup_md"):
                print(f"  followup: {seg['optional_followup_md']}")
            for opt in seg.get("path_options", []):
                print(f"  option {opt['key']}: {opt['label_md']}")

    dump("stage4_parsed", parsed_segments)

    # Now resolve each segment. For Maya, we treat both as 'specific' and use
    # the implicit intent + dedup verdict from parse — overriding only where the
    # parser is clearly wrong (see persona.md: she explicitly does NOT have
    # dynamical-systems mastery, so 'consolidate' should be 'teach').
    resolved = []
    for entry in parsed_segments:
        raw = entry["raw_text"]
        for seg in entry["response"]["segments"]:
            final_intent_text = seg["raw_text_segment"]
            # Maya elaborates via the optional followup. We mimic that by
            # tacking her clarification onto final_intent_text — this is
            # what the UI passes when the user types into the followup field.
            if "dynamical systems" in raw.lower():
                final_intent_text = (
                    seg["raw_text_segment"]
                    + " Coming at it from the neuroscience application side — "
                    "I want to model neural circuits — but I genuinely don't "
                    "have this material yet, I want to learn it."
                )
            intent_context = seg["draft_intent_context"]
            existing_slug = None
            related_slug = None
            if seg["dedup"]["verdict"] == "same":
                existing_slug = seg["dedup"]["matched_node_slug"]
            elif seg["dedup"]["verdict"] == "related":
                related_slug = seg["dedup"]["matched_node_slug"]
            payload = {
                "user_id": USER_ID,
                "added_via": "survey",
                "raw_text": raw,
                "final_intent_text": final_intent_text,
                "intent_context": intent_context,
                "existing_node_slug": existing_slug,
                "related_node_slug": related_slug,
            }
            print(f"\n--- resolving: {final_intent_text[:60]} (verdict={seg['dedup']['verdict']})")
            r = api_post("/add-interest/resolve", payload, timeout=180.0)
            print(f"  → node: {r['node_slug']} ({r['verdict']})")
            print(f"  starter: {r['starter_preview_md']}")
            print(f"  tour tiles: {len(r['concept_tour'])}")
            for t in r["concept_tour"]:
                print(f"    [{t['node_slug']}] {t['name']} — {t.get('gloss') or ''}")
            resolved.append({"raw": raw, "request": payload, "response": r})
    dump("stage4_resolved", resolved)


# ============================================================
# Stage 5 — Concept tour subtopic states
# ============================================================
def stage5():
    """Maya responds to each tile with familiar / refresh / new.

    The script encodes Maya's expected responses (see persona.md).
    """
    client = sb()
    resolved = json.loads((OUT_DIR / "stage4_resolved.json").read_text())

    # Maya's response table by subtopic name (case-insensitive substring match).
    # Per persona:
    # Familiar: matrices, vectors, dot product, separation of variables, PDFs,
    #           expectation, variance
    # Refresh: eigenvalues, eigenvectors, linear ODE systems, matrix
    #          exponentials, stability, conditional probability, Bayes
    # New: entropy, mutual information, KL divergence, bifurcations,
    #      phase portrait, manifolds, tensors
    FAMILIAR = [
        "matrix", "matrices", "vectors", "dot product",
        "separation of variables", "pdf", "probability density",
        "expectation", "variance", "mean",
    ]
    REFRESH = [
        "eigen", "linear ode", "linear odes", "matrix exponential",
        "stability", "conditional probability", "bayes",
        "second-order ode", "system of ode",
    ]
    NEW = [
        "entropy", "mutual information", "kl divergence", "kullback",
        "bifurcat", "phase portrait", "manifold", "tensor", "channel capacity",
        "information measure",
    ]

    def classify(name: str) -> str:
        n = name.lower()
        for k in NEW:
            if k in n:
                return "new"
        for k in REFRESH:
            if k in n:
                return "refresh"
        for k in FAMILIAR:
            if k in n:
                return "familiar"
        # default: refresh (Maya is curious, marks rusty things as refresh)
        return "refresh"

    all_tiles = []
    seen = set()  # dedup across tours
    for entry in resolved:
        for tile in entry["response"]["concept_tour"]:
            key = (tile["node_slug"], tile["subtopic_key"])
            if key in seen:
                continue
            seen.add(key)
            state = classify(tile["name"])
            all_tiles.append({**tile, "_state": state, "_interest": entry["response"]["node_slug"]})

    # Write user_subtopic_states rows
    rows = [
        {
            "user_id": USER_ID,
            "node_id": t["node_id"],
            "subtopic_slug": t["subtopic_key"],
            "state": t["_state"],
        }
        for t in all_tiles
    ]
    client.table("user_subtopic_states").upsert(
        rows, on_conflict="user_id,node_id,subtopic_slug"
    ).execute()

    # Map to user_node_states bumps:
    # familiar → comfortable (only bump if currently unseen)
    # refresh → active (only bump if currently unseen)
    # new → unseen (no change)
    # But never *downgrade* — leave Stage 2 'active' marks alone.
    current = (
        client.table("user_node_states")
        .select("node_id, state")
        .eq("user_id", USER_ID)
        .execute()
    )
    current_state = {r["node_id"]: r["state"] for r in current.data}

    # For each prereq node that the tour visits, aggregate the tile responses
    # to decide a node-level state. Rule:
    # - if any tile is "refresh", node becomes 'active' (or stays at higher)
    # - if all tiles are "familiar", node becomes 'comfortable'
    # - if all tiles are "new", leave as 'unseen'
    from collections import defaultdict
    per_node = defaultdict(list)
    for t in all_tiles:
        per_node[t["node_id"]].append(t["_state"])

    node_state_updates = []
    for node_id, states in per_node.items():
        if "refresh" in states:
            new_state = "active"
        elif all(s == "familiar" for s in states):
            new_state = "comfortable"
        else:
            continue  # leave as unseen
        existing = current_state.get(node_id)
        if existing in ("comfortable",) and new_state == "active":
            continue  # don't downgrade
        if existing == new_state:
            continue
        node_state_updates.append({"user_id": USER_ID, "node_id": node_id, "state": new_state})

    if node_state_updates:
        client.table("user_node_states").upsert(
            node_state_updates, on_conflict="user_id,node_id"
        ).execute()

    # comfort_responses_json on survey row
    comfort = {
        "subtopics": {
            f"{t['node_slug']}:{t['subtopic_key']}": t["_state"] for t in all_tiles
        }
    }
    client.table("surveys").update(
        {
            "comfort_responses_json": comfort,
            "completed_stages": ["stage1", "stage2", "stage3", "stage4", "stage5"],
        }
    ).eq("user_id", USER_ID).execute()

    dump("stage5_tiles", all_tiles)
    print(f"OK — {len(all_tiles)} subtopic states written; "
          f"{len(node_state_updates)} node-level bumps")
    print("Per-node summary:")
    for node_id, states in per_node.items():
        n = next(t for t in all_tiles if t["node_id"] == node_id)
        from collections import Counter
        c = Counter(states)
        print(f"  {n['node_slug']}: {dict(c)}")


# ============================================================
# Stage 6 — Mode balance
# ============================================================
def stage6():
    client = sb()
    # Maya: slight problems-lean. mode_balance interpretation per ARCHITECTURE
    # is 0.0=all problems, 1.0=all papers. So 0.45 = a hair more problems.
    client.table("surveys").update(
        {
            "mode_balance": 0.45,
            "completed_stages": [
                "stage1", "stage2", "stage3", "stage4", "stage5", "stage6",
            ],
        }
    ).eq("user_id", USER_ID).execute()
    print("OK — mode_balance = 0.45 (slight problems lean)")


# ============================================================
# Stage 7 — Confirm graph slice (read-only)
# ============================================================
def stage7():
    client = sb()
    interests = (
        client.table("user_interests")
        .select("node_id, intent_context, added_via")
        .eq("user_id", USER_ID)
        .execute()
    )
    interest_node_ids = [r["node_id"] for r in interests.data]
    states = (
        client.table("user_node_states")
        .select("node_id, state")
        .eq("user_id", USER_ID)
        .execute()
    )
    # 1-hop neighbours
    edges = (
        client.table("edges")
        .select("source_node_id, target_node_id, edge_kind")
        .execute()
    )
    edges_all = edges.data
    user_node_ids = set(interest_node_ids) | {r["node_id"] for r in states.data}
    neighbours: set[str] = set()
    user_edges = []
    for e in edges_all:
        s, t = e["source_node_id"], e["target_node_id"]
        if s in user_node_ids or t in user_node_ids:
            user_edges.append(e)
            if s in user_node_ids:
                neighbours.add(t)
            if t in user_node_ids:
                neighbours.add(s)
    all_ids = user_node_ids | neighbours
    nodes = (
        client.table("nodes")
        .select("id, slug, title, kind, domain")
        .in_("id", list(all_ids))
        .execute()
    )
    nodes_by_id = {n["id"]: n for n in nodes.data}
    states_by_id = {r["node_id"]: r["state"] for r in states.data}

    yours = []
    adjacent = []
    for nid in all_ids:
        n = nodes_by_id.get(nid)
        if not n:
            continue
        in_slice = nid in user_node_ids
        entry = {
            "slug": n["slug"],
            "title": n["title"],
            "kind": n["kind"],
            "domain": n["domain"],
            "state": states_by_id.get(nid, "unseen"),
            "is_interest": nid in interest_node_ids,
        }
        if in_slice:
            yours.append(entry)
        else:
            adjacent.append(entry)

    print("YOUR SLICE:")
    for e in sorted(yours, key=lambda x: (x["kind"], x["slug"])):
        tag = " [INTEREST]" if e["is_interest"] else ""
        print(f"  ({e['kind']:>10}) {e['slug']:30} {e['state']:>12}{tag}  — {e['title']}")
    print(f"\nADJACENT 1-HOP ({len(adjacent)}):")
    for e in sorted(adjacent, key=lambda x: x["slug"]):
        print(f"  ({e['kind']:>10}) {e['slug']:30}  — {e['title']}")

    dump("stage7_slice", {"yours": yours, "adjacent": adjacent, "edges": user_edges})


# ============================================================
# Cold-start curator
# ============================================================
def cold_start():
    payload = {"user_id": USER_ID, "triggered_by": "cold_start"}
    resp = api_post("/run-daily-planner", payload, timeout=600.0)
    dump("cold_start_planner", resp)
    print(json.dumps(resp, indent=2))


# ============================================================
# Surface daily
# ============================================================
def surface_daily():
    payload = {"user_id": USER_ID}
    resp = api_post("/surface-daily", payload, timeout=120.0)
    dump("surface_daily", resp)
    print(json.dumps(resp, indent=2, default=str))


# ============================================================
# Inspect surfaced content
# ============================================================
def inspect():
    client = sb()
    surfaced = json.loads((OUT_DIR / "surface_daily.json").read_text())
    items = surfaced["items"]
    print(f"Inspecting {len(items)} surfaced items")

    report = []
    for item in items:
        qiid = item["queue_item_id"]
        kind = item["kind"]
        ref_id = item.get("ref_id")
        qi = (
            client.table("queue_items")
            .select("*")
            .eq("id", qiid)
            .single()
            .execute()
        ).data
        record = {
            "queue_item": qi,
            "added_reason": qi.get("added_reason"),
            "kind": kind,
            "details": None,
        }
        if kind == "problem":
            prob = (
                client.table("problems")
                .select("id, title, statement_md, context_md, tags, intent, difficulty, topic_node_id")
                .eq("id", ref_id)
                .single()
                .execute()
            ).data
            hints = (
                client.table("problem_hints")
                .select("level, text")
                .eq("problem_id", ref_id)
                .order("level")
                .execute()
            ).data
            node_id = prob.get("topic_node_id")
            node = None
            if node_id:
                node = (
                    client.table("nodes")
                    .select("slug, title, kind")
                    .eq("id", node_id)
                    .single()
                    .execute()
                ).data
            record["details"] = {"problem": prob, "hints": hints, "topic_node": node}
        elif kind == "paper_engagement":
            eng = (
                client.table("paper_engagements")
                .select("*")
                .eq("id", ref_id)
                .single()
                .execute()
            ).data
            paper = (
                client.table("papers")
                .select("id, title, authors_json, year, arxiv_id, doi, abstract_md")
                .eq("id", eng["paper_id"])
                .single()
                .execute()
            ).data
            record["details"] = {"engagement": eng, "paper": paper}
        elif kind == "concept_review":
            node = (
                client.table("nodes")
                .select("id, slug, title, kind, description_md, subtopics_json")
                .eq("id", ref_id)
                .single()
                .execute()
            ).data
            brief = (
                client.table("node_concept_briefs")
                .select("brief_md, subtopic_glosses_json")
                .eq("node_id", ref_id)
                .execute()
            ).data
            record["details"] = {"node": node, "brief": brief[0] if brief else None}
        elif kind == "refresher":
            # ref_id is a node (curator emits this)
            node_id = ref_id
            node = (
                client.table("nodes")
                .select("id, slug, title, kind, description_md, subtopics_json")
                .eq("id", node_id)
                .single()
                .execute()
            ).data
            record["details"] = {"node": node}
        report.append(record)

    dump("inspect_report", report)
    for r in report:
        print(f"\n=========== {r['kind']} (queue_item {r['queue_item']['id'][:8]}) =============")
        print(f"added_reason: {r['added_reason']}")
        if r["kind"] == "problem":
            p = r["details"]["problem"]
            print(f"title: {p['title']}")
            print(f"intent: {p['intent']}  difficulty: {p['difficulty']}")
            print(f"tags: {p['tags']}")
            topic_node = r["details"]["topic_node"]
            if topic_node:
                print(f"topic_node: {topic_node['slug']} ({topic_node['kind']})")
            print(f"context_md:\n{p.get('context_md') or '(none)'}")
            print(f"statement_md:\n{p['statement_md']}")
            print(f"\nhints ({len(r['details']['hints'])}):")
            for h in r['details']['hints']:
                print(f"  L{h['level']}: {h['text']}")
        elif r["kind"] == "paper_engagement":
            paper = r["details"]["paper"]
            eng = r["details"]["engagement"]
            print(f"paper: {paper['title']} ({paper['year']})")
            print(f"authors: {paper['authors_json']}")
            print(f"why_this_md:\n{eng['why_this_md']}")
            print(f"orienting_concepts_json:")
            for c in eng.get("orienting_concepts_json") or []:
                if isinstance(c, dict):
                    print(f"  - {c.get('term')}: {c.get('definition_md')}")
                else:
                    print(f"  - {c}")
            print("questions:")
            for q in eng.get("questions_json") or []:
                print(f"  [{q.get('kind')}] {q.get('prompt_md')}")
        elif r["kind"] == "concept_review":
            node = r["details"]["node"]
            print(f"node: {node['slug']} ({node['kind']}): {node['title']}")
            print(f"description_md: {node['description_md']}")
            brief = r["details"].get("brief")
            if brief:
                print(f"brief_md:\n{brief['brief_md']}")
                print("subtopic glosses:")
                for g in brief.get("subtopic_glosses_json") or []:
                    print(f"  - {g.get('title')}: {g.get('gloss_md')}")
            else:
                print("(no concept_brief cached)")
        elif r["kind"] == "refresher":
            node = r["details"]["node"]
            print(f"node: {node['slug']} ({node['kind']}): {node['title']}")
            print(f"description_md: {node['description_md']}")


# ============================================================
def main():
    if len(sys.argv) < 2:
        print("usage: walkthrough.py <stage>")
        return
    fn = {
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
        "stage4": stage4,
        "stage5": stage5,
        "stage6": stage6,
        "stage7": stage7,
        "cold_start": cold_start,
        "surface_daily": surface_daily,
        "inspect": inspect,
    }[sys.argv[1]]
    fn()


if __name__ == "__main__":
    main()
