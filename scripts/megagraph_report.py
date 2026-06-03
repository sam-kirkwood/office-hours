"""Read-only snapshot of the current megagraph state, for curation review.

Usage:
    uv run --project api python scripts/megagraph_report.py

Prints: node counts (by kind / domain / seeded-vs-user), the foundation list,
every interest node with its in/out edge degree and provenance, an orphan
report (interest nodes with no edges), per-domain interest density (the signal
Stage-3 suggestion surfacing depends on), and the full edge adjacency.

Env: reads SUPABASE_URL and SUPABASE_SECRET_KEY from api/.env or process env.
Makes no writes.
"""
from __future__ import annotations

import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from supabase import create_client

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        out[key.strip()] = val.strip().strip("'\"")
    return out


def _get_supabase():
    env = _load_dotenv(REPO_ROOT / "api" / ".env")
    url = os.environ.get("SUPABASE_URL") or env.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set (env or api/.env)")
    return create_client(url, key)


def main() -> None:
    sb = _get_supabase()
    nodes = sb.table("nodes").select(
        "id, slug, title, kind, domain, difficulty_hint, created_by_user_id, pool_status"
    ).execute().data or []
    edges = sb.table("edges").select(
        "source_node_id, target_node_id, edge_kind"
    ).execute().data or []

    by_id = {n["id"]: n for n in nodes}
    foundations = sorted([n for n in nodes if n["kind"] == "foundation"], key=lambda n: (n["domain"], n["slug"]))
    interests = sorted([n for n in nodes if n["kind"] == "interest"], key=lambda n: (n["domain"], n["slug"]))

    # Degree bookkeeping.
    out_deg: dict[str, Counter] = defaultdict(Counter)   # source -> {kind: count}
    in_deg: dict[str, Counter] = defaultdict(Counter)    # target -> {kind: count}
    for e in edges:
        out_deg[e["source_node_id"]][e["edge_kind"]] += 1
        in_deg[e["target_node_id"]][e["edge_kind"]] += 1

    def total_deg(nid: str) -> int:
        return sum(out_deg[nid].values()) + sum(in_deg[nid].values())

    # ---- Summary ----------------------------------------------------------
    print("=" * 72)
    print("MEGAGRAPH SNAPSHOT")
    print("=" * 72)
    print(f"Total nodes: {len(nodes)}   ({len(foundations)} foundation, {len(interests)} interest)")
    print(f"Total edges: {len(edges)}")
    ek = Counter(e["edge_kind"] for e in edges)
    print(f"  by kind: " + ", ".join(f"{k}={v}" for k, v in sorted(ek.items())))
    seeded = sum(1 for n in interests if n.get("created_by_user_id") is None)
    print(f"Interest provenance: {seeded} seeded (created_by_user_id=NULL), {len(interests) - seeded} user-created")
    dom = Counter(n["domain"] for n in interests)
    print(f"Interest nodes by domain: " + ", ".join(f"{k}={v}" for k, v in sorted(dom.items())))
    diff = Counter(n.get("difficulty_hint") for n in interests)
    print(f"Interest nodes by difficulty: " + ", ".join(f"{k}={v}" for k, v in sorted(diff.items(), key=lambda x: str(x[0]))))

    # ---- Foundations ------------------------------------------------------
    print("\n" + "-" * 72)
    print("FOUNDATION NODES")
    print("-" * 72)
    for n in foundations:
        print(f"  [{n['domain']:>7}] {n['slug']:<32} in:{sum(in_deg[n['id']].values())} out:{sum(out_deg[n['id']].values())}")

    # ---- Interest nodes ---------------------------------------------------
    print("\n" + "-" * 72)
    print("INTEREST NODES  (prq=prereq edges in, rel=related edges, →=feeds-out)")
    print("-" * 72)
    for n in interests:
        nid = n["id"]
        prov = "seed" if n.get("created_by_user_id") is None else "USER"
        pstat = n.get("pool_status") or "?"
        marker = "  " if total_deg(nid) else "!!"  # orphan flag
        print(
            f" {marker}[{n['domain']:>7}/{(n.get('difficulty_hint') or '?'):<8}] "
            f"{n['slug']:<40} "
            f"prq_in:{in_deg[nid]['prerequisite']} rel:{in_deg[nid]['related'] + out_deg[nid]['related']} "
            f"feeds:{out_deg[nid]['prerequisite']}  [{prov}|{pstat}]"
        )

    # ---- Orphans ----------------------------------------------------------
    orphans = [n for n in interests if total_deg(n["id"]) == 0]
    print("\n" + "-" * 72)
    print(f"ORPHAN INTEREST NODES (no edges at all): {len(orphans)}")
    print("-" * 72)
    for n in orphans:
        print(f"  {n['slug']}  ({n['domain']})")
    if not orphans:
        print("  (none)")

    # ---- Per-domain interest density (Stage-3 surfacing signal) -----------
    print("\n" + "-" * 72)
    print("PER-DOMAIN INTEREST DENSITY  (Stage-3 needs >= 6 per domain to fill)")
    print("-" * 72)
    for d in sorted({n["domain"] for n in interests}):
        active = [n for n in interests if n["domain"] == d and (n.get("pool_status") or "active") == "active"]
        flag = "" if len(active) >= 6 else "  <-- thin"
        print(f"  {d:>7}: {len(active)} active interest nodes{flag}")

    # ---- Full edge adjacency ----------------------------------------------
    print("\n" + "-" * 72)
    print("EDGES")
    print("-" * 72)
    def slug(nid: str) -> str:
        n = by_id.get(nid)
        return n["slug"] if n else f"?{nid[:8]}"
    for e in sorted(edges, key=lambda e: (e["edge_kind"], slug(e["source_node_id"]), slug(e["target_node_id"]))):
        print(f"  {slug(e['source_node_id']):<40} -> {slug(e['target_node_id']):<40} ({e['edge_kind']})")


if __name__ == "__main__":
    main()
