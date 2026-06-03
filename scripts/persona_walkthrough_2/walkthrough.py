"""Persona-2 walkthrough: Hank Lindqvist, a quant taking semi-retirement.

Physics-and-math interest profile (matches the "currently only physics and
math available" copy). See persona.md.

Run stages individually:
    uv run --project api python scripts/persona_walkthrough_2/walkthrough.py <stage>
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
from supabase import create_client

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

USER_ID = "4ca9260e-8b61-4db6-b706-2f7acfcbe781"  # Hank — auth.users id
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


def api_post(path, payload, timeout=120.0):
    r = httpx.post(
        f"{API_BASE}{path}",
        json=payload,
        headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"},
        timeout=timeout,
    )
    if r.status_code >= 400:
        print(f"!! {path} → {r.status_code}\n{r.text[:1000]}")
        r.raise_for_status()
    return r.json()


def dump(name, obj):
    p = OUT_DIR / f"{name}.json"
    p.write_text(json.dumps(obj, indent=2, default=str))
    print(f"wrote {p}")


# ============================================================
def stage1():
    client = sb()
    background = {
        "domains": [
            {
                "key": "physics",
                "subareas": [
                    "classical-mechanics", "electromagnetism", "quantum",
                    "thermo-stat-mech", "condensed-matter",
                ],
                "relationship": "studied_reconnecting",
            },
            {
                "key": "mathematics",
                "subareas": [
                    "calculus-analysis", "linear-algebra", "odes-pdes",
                    "probability-stats",
                ],
                "relationship": "encounter_at_work",
            },
        ]
    }
    free_text = (
        "Quant taking semi-retirement next year. Physics undergrad 30 "
        "years ago, been doing applied math in finance since. My math is "
        "solid — calculus, linear algebra, probability are daily tools — "
        "but my physics has faded to almost nothing. I want to actually "
        "do statistical mechanics properly: partition functions, the "
        "Ising model, phase transitions, eventually renormalization "
        "group. I've been using Boltzmann distributions analogically in "
        "market models for years but never derived them from scratch."
    )
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
    survey = client.table("surveys").select("*").eq("user_id", USER_ID).single().execute()
    dump("stage1_survey", survey.data)
    print("OK — stage 1 written")


# ============================================================
def stage2():
    client = sb()
    refresh_slugs = [
        "classical-mechanics", "electromagnetism-1", "quantum-mechanics-1",
        "statistical-mechanics", "thermodynamics",
    ]
    nodes = (
        client.table("nodes").select("id, slug, title").in_("slug", refresh_slugs).execute()
    )
    print("matched foundation nodes:", [(n["slug"], n["title"]) for n in nodes.data])
    rows = [{"user_id": USER_ID, "node_id": n["id"], "state": "active"} for n in nodes.data]
    client.table("user_node_states").upsert(rows, on_conflict="user_id,node_id").execute()
    ratings = {n["slug"]: "refresh" for n in nodes.data}
    client.table("surveys").update(
        {"node_ratings_json": ratings, "completed_stages": ["stage1", "stage2"]}
    ).eq("user_id", USER_ID).execute()
    dump("stage2_marked_nodes", [n["slug"] for n in nodes.data])
    print(f"OK — {len(nodes.data)} nodes marked active")


# ============================================================
def stage3():
    client = sb()
    marked = (
        client.table("user_node_states")
        .select("node_id")
        .eq("user_id", USER_ID)
        .eq("state", "active")
        .execute()
    )
    marked_ids = [r["node_id"] for r in marked.data]
    domains = [
        {
            "key": "physics",
            "label": "Physics",
            "subarea_labels": [
                "Classical mechanics", "Electromagnetism", "Quantum",
                "Thermo & stat mech", "Condensed matter",
            ],
            "relationship_label": "I studied this",
        },
        {
            "key": "mathematics",
            "label": "Mathematics",
            "subarea_labels": [
                "Calculus & analysis", "Linear algebra", "ODEs & PDEs",
                "Probability & stats",
            ],
            "relationship_label": "I encounter this in my work",
        },
    ]
    payload = {
        "user_id": USER_ID,
        "domains": domains,
        "marked_foundation_node_ids": marked_ids,
    }
    resp = api_post("/survey/suggest-interests", payload, timeout=120.0)
    dump("stage3_suggestions", resp)
    print(f"OK — {len(resp['suggestions'])} suggestions:")
    for s in resp["suggestions"]:
        print(f"  - {s['title']}: {s['why_suggested_md']}")


# ============================================================
def stage4():
    """Hank ignores the suggestions and types two free-text interests."""
    suggestions = json.loads((OUT_DIR / "stage3_suggestions.json").read_text())
    print("Suggestions returned:")
    for s in suggestions["suggestions"]:
        print(f"  {s['slug']}: {s['title']}")

    raw_inputs = [
        # The on-ramp
        "Phase transitions and critical phenomena — the Ising model in 1D "
        "and 2D, mean-field theory, scaling laws, universality classes.",
        # The stretch
        "Renormalization group — Wilson's approach, fixed points of the "
        "RG, why it explains critical phenomena, when it works.",
    ]

    parsed = []
    for raw in raw_inputs:
        print(f"\n--- parsing: {raw[:60]}...")
        resp = api_post(
            "/add-interest/parse",
            {"user_id": USER_ID, "raw_text": raw, "added_via": "survey"},
            timeout=120.0,
        )
        parsed.append({"raw_text": raw, "response": resp})
        for seg in resp["segments"]:
            print(f"  mirror: {seg['mirror_back_md']}")
            print(f"  dedup={seg['dedup']}, intent={seg['implicit_intent']}, specificity={seg['specificity']}")
            if seg.get("optional_followup_md"):
                print(f"  followup: {seg['optional_followup_md']}")
            for opt in seg.get("path_options", []):
                print(f"  option {opt['key']}: {opt['label_md']}")
    dump("stage4_parsed", parsed)

    resolved = []
    for entry in parsed:
        raw = entry["raw_text"]
        for seg in entry["response"]["segments"]:
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
                "final_intent_text": seg["raw_text_segment"],
                "intent_context": seg["draft_intent_context"],
                "existing_node_slug": existing_slug,
                "related_node_slug": related_slug,
            }
            print(f"\n--- resolving: {seg['raw_text_segment'][:60]} (verdict={seg['dedup']['verdict']})")
            r = api_post("/add-interest/resolve", payload, timeout=180.0)
            print(f"  -> node: {r['node_slug']} ({r['verdict']})")
            print(f"  starter: {r['starter_preview_md']}")
            print(f"  tour tiles: {len(r['concept_tour'])}")
            for t in r["concept_tour"]:
                print(f"    [{t['node_slug']}] {t['name']} — {t.get('gloss') or ''}")
            resolved.append({"raw": raw, "request": payload, "response": r})
    dump("stage4_resolved", resolved)


# ============================================================
def stage5():
    client = sb()
    resolved = json.loads((OUT_DIR / "stage4_resolved.json").read_text())

    # Hank's tile responses by keyword. Math subtopics he uses daily: familiar.
    # Physics undergrad rust: refresh. Genuine new gaps: new.
    FAMILIAR = [
        # Math he uses daily
        "linear", "matrix", "matrices", "eigen", "vector", "derivative",
        "integral", "differentiation", "integration", "ode", "pde",
        "fourier", "complex", "limit", "continuity",
        "probability", "random variable", "expectation", "variance",
        "distribution", "regression",
        # Stat-mech basics he half-recalls
        "boltzmann distribution", "partition function",
        # Thermo basics
        "first law", "entropy",
    ]
    REFRESH = [
        # Physics undergrad apparatus
        "lagrangian", "hamiltonian", "newton",
        "maxwell", "electromagnetic", "gauss", "ampere", "faraday",
        "schrodinger", "schrödinger", "wavefunction", "operator", "commutator",
        "ensemble", "canonical", "microcanonical", "grand canonical",
        "free energy", "helmholtz", "gibbs",
        "thermodynamic potential", "heat capacity", "phase",
    ]
    NEW = [
        # Things he's never properly done
        "renormalization", "renormalisation", "scaling exponent",
        "ising", "block spin", "fixed point", "universality",
        "rg flow", "critical exponent", "mean field",
    ]

    def classify(name):
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
        # Hank's default: he's an undergrad-trained physicist so most things
        # he half-knows. Default to refresh.
        return "refresh"

    all_tiles = []
    seen = set()
    for entry in resolved:
        for tile in entry["response"]["concept_tour"]:
            key = (tile["node_slug"], tile["subtopic_key"])
            if key in seen:
                continue
            seen.add(key)
            all_tiles.append({
                **tile,
                "_state": classify(tile["name"]),
                "_interest": entry["response"]["node_slug"],
            })

    if all_tiles:
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

    # Aggregate to node-level (same rule as persona 1)
    from collections import defaultdict, Counter
    per_node = defaultdict(list)
    for t in all_tiles:
        per_node[t["node_id"]].append(t["_state"])

    current = (
        client.table("user_node_states").select("node_id, state").eq("user_id", USER_ID).execute()
    )
    current_state = {r["node_id"]: r["state"] for r in current.data}
    bumps = []
    for node_id, states in per_node.items():
        if "refresh" in states:
            new = "active"
        elif all(s == "familiar" for s in states):
            new = "comfortable"
        else:
            continue
        if current_state.get(node_id) == new:
            continue
        if current_state.get(node_id) == "comfortable" and new == "active":
            continue
        bumps.append({"user_id": USER_ID, "node_id": node_id, "state": new})
    if bumps:
        client.table("user_node_states").upsert(bumps, on_conflict="user_id,node_id").execute()

    comfort = {
        "subtopics": {
            f"{t['node_slug']}:{t['subtopic_key']}": t["_state"] for t in all_tiles
        }
    }
    client.table("surveys").update({
        "comfort_responses_json": comfort,
        "completed_stages": [
            "stage1", "stage2", "stage3", "stage4", "stage5",
        ],
    }).eq("user_id", USER_ID).execute()
    dump("stage5_tiles", all_tiles)
    print(f"OK — {len(all_tiles)} tiles; {len(bumps)} node-level bumps")
    print("Per-node summary:")
    for node_id, states in per_node.items():
        n = next(t for t in all_tiles if t["node_id"] == node_id)
        print(f"  {n['node_slug']}: {dict(Counter(states))}")


# ============================================================
def stage6():
    client = sb()
    client.table("surveys").update({
        "mode_balance": 0.5,
        "completed_stages": [
            "stage1", "stage2", "stage3", "stage4", "stage5", "stage6",
        ],
    }).eq("user_id", USER_ID).execute()
    print("OK — mode_balance = 0.5 (default)")


# ============================================================
def stage7():
    client = sb()
    interests = client.table("user_interests").select("node_id, intent_context").eq("user_id", USER_ID).execute().data
    interest_ids = [r["node_id"] for r in interests]
    states = client.table("user_node_states").select("node_id, state").eq("user_id", USER_ID).execute().data
    edges = client.table("edges").select("source_node_id, target_node_id, edge_kind").execute().data

    user_ids = set(interest_ids) | {r["node_id"] for r in states}
    neighbours = set()
    user_edges = []
    for e in edges:
        if e["source_node_id"] in user_ids or e["target_node_id"] in user_ids:
            user_edges.append(e)
            if e["source_node_id"] in user_ids:
                neighbours.add(e["target_node_id"])
            if e["target_node_id"] in user_ids:
                neighbours.add(e["source_node_id"])
    all_ids = user_ids | neighbours
    nodes = client.table("nodes").select("id, slug, title, kind, domain").in_("id", list(all_ids)).execute().data
    nodes_by_id = {n["id"]: n for n in nodes}
    states_by_id = {r["node_id"]: r["state"] for r in states}

    yours = []
    adjacent = []
    for nid in all_ids:
        n = nodes_by_id.get(nid)
        if not n:
            continue
        entry = {
            "slug": n["slug"], "title": n["title"], "kind": n["kind"],
            "domain": n["domain"],
            "state": states_by_id.get(nid, "unseen"),
            "is_interest": nid in interest_ids,
        }
        if nid in user_ids:
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
def cold_start():
    resp = api_post(
        "/run-daily-planner",
        {"user_id": USER_ID, "triggered_by": "cold_start"},
        timeout=600.0,
    )
    dump("cold_start_planner", resp)
    print(json.dumps(resp, indent=2))


def surface_daily():
    resp = api_post("/surface-daily", {"user_id": USER_ID}, timeout=120.0)
    dump("surface_daily", resp)
    print(json.dumps(resp, indent=2, default=str))


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
        qi = client.table("queue_items").select("*").eq("id", qiid).single().execute().data
        record = {"queue_item": qi, "added_reason": qi.get("added_reason"),
                  "kind": kind, "details": None}
        if kind == "problem":
            prob = client.table("problems").select(
                "id, title, statement_md, context_md, tags, intent, difficulty, topic_node_id"
            ).eq("id", ref_id).single().execute().data
            hints = client.table("problem_hints").select("level, text").eq("problem_id", ref_id).order("level").execute().data
            node = None
            if prob.get("topic_node_id"):
                node = client.table("nodes").select("slug, title, kind").eq("id", prob["topic_node_id"]).single().execute().data
            record["details"] = {"problem": prob, "hints": hints, "topic_node": node}
        elif kind == "paper_engagement":
            eng = client.table("paper_engagements").select("*").eq("id", ref_id).single().execute().data
            paper = client.table("papers").select("*").eq("id", eng["paper_id"]).single().execute().data
            record["details"] = {"engagement": eng, "paper": paper}
        elif kind == "concept_review":
            node = client.table("nodes").select("*").eq("id", ref_id).single().execute().data
            brief = client.table("node_concept_briefs").select("*").eq("node_id", ref_id).execute().data
            record["details"] = {"node": node, "brief": brief[0] if brief else None}
        elif kind == "refresher":
            node = client.table("nodes").select("*").eq("id", ref_id).single().execute().data
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
            tn = r["details"]["topic_node"]
            if tn:
                print(f"topic_node: {tn['slug']} ({tn['kind']})")
            print(f"context_md:\n{p.get('context_md') or '(none)'}")
            print(f"statement_md:\n{p['statement_md']}")
            print(f"\nhints ({len(r['details']['hints'])}):")
            for h in r['details']['hints']:
                print(f"  L{h['level']}: {h['text']}")
        elif r["kind"] == "paper_engagement":
            paper = r["details"]["paper"]
            eng = r["details"]["engagement"]
            print(f"paper: {paper['title']} ({paper.get('year')})")
            print(f"authors: {paper.get('authors_json')}")
            print(f"why_this_md:\n{eng.get('why_this_md')}")
            print("orienting_concepts_json:")
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
            print(f"description_md:\n{node['description_md']}")
            brief = r["details"].get("brief")
            if brief:
                print(f"\nbrief_md:\n{brief['brief_md']}")
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
def queue_summary():
    """Dump all queue items for the user (for review of what wasn't surfaced)."""
    client = sb()
    q = client.table("queue_items").select(
        "id, kind, ref_id, state, priority_score, added_reason"
    ).eq("user_id", USER_ID).order("added_at").execute().data
    print(f"All queue items ({len(q)}):")
    for item in q:
        title = "?"
        if item["kind"] == "problem":
            p = client.table("problems").select("title, intent, tags").eq("id", item["ref_id"]).execute().data
            if p:
                title = f"{p[0]['title']} [{p[0]['intent']}] tags={p[0]['tags']}"
        elif item["kind"] in ("refresher", "concept_review", "suggested_interest"):
            n = client.table("nodes").select("slug, title").eq("id", item["ref_id"]).execute().data
            if n:
                title = f"{n[0]['slug']} ({n[0]['title']})"
        elif item["kind"] == "paper_engagement":
            e = client.table("paper_engagements").select("paper_id").eq("id", item["ref_id"]).execute().data
            if e:
                p = client.table("papers").select("title").eq("id", e[0]["paper_id"]).execute().data
                if p:
                    title = f"paper: {p[0]['title']}"
        print(f"\n  id={item['id'][:8]} kind={item['kind']:>10} state={item['state']:>10} pri={item['priority_score']}")
        print(f"    {title}")
        print(f"    reason: {(item.get('added_reason') or '')[:200]}")


# ============================================================
def main():
    if len(sys.argv) < 2:
        print("usage: walkthrough.py <stage>")
        return
    fn = {
        "stage1": stage1, "stage2": stage2, "stage3": stage3,
        "stage4": stage4, "stage5": stage5, "stage6": stage6,
        "stage7": stage7, "cold_start": cold_start,
        "surface_daily": surface_daily, "inspect": inspect,
        "queue_summary": queue_summary,
    }[sys.argv[1]]
    fn()


if __name__ == "__main__":
    main()
