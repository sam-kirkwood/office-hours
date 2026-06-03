"""Load YAML seed files from supabase/seeds/interests/ into the megagraph.

Usage:
    uv run --project api python scripts/seed_megagraph.py --dry-run
    uv run --project api python scripts/seed_megagraph.py --apply
    uv run --project api python scripts/seed_megagraph.py --reclaim-slug <slug>

Idempotent: re-running with the same YAMLs produces no DB changes.

Conventions:
- Every seeded node is written with created_by_user_id = NULL — the marker
  for system-curated rows. The weekly curation report ignores these.
- Edges are written one row at a time (not batched) so a single unique-
  violation doesn't roll back the entire seed pass. Matches the fix landed
  in Step 9b for the same anti-pattern in add_interest.py.
- prereq_slugs produce edge_kind='prerequisite'; related_slugs produce
  edge_kind='related'.

Env: reads SUPABASE_URL and SUPABASE_SECRET_KEY from api/.env or process env.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml
from supabase import Client, create_client

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "supabase" / "seeds" / "interests"


# ---------------------------------------------------------------------------
# env loading
# ---------------------------------------------------------------------------


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


def _get_supabase() -> Client:
    import os
    env = _load_dotenv(REPO_ROOT / "api" / ".env")
    url = os.environ.get("SUPABASE_URL") or env.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY") or env.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        sys.exit("ERROR: SUPABASE_URL and SUPABASE_SECRET_KEY must be set (env or api/.env)")
    return create_client(url, key)


# ---------------------------------------------------------------------------
# YAML loading + validation
# ---------------------------------------------------------------------------


REQUIRED_KEYS = ("slug", "title", "domain", "difficulty_hint", "description_md", "subtopics", "prereq_slugs")
VALID_DOMAINS = ("math", "physics", "applied")
VALID_DIFFICULTIES = ("intro", "core", "advanced")


def _validate(data: dict[str, Any], known_slugs: set[str]) -> str | None:
    for k in REQUIRED_KEYS:
        if k not in data:
            return f"missing required key: {k}"
    if data["domain"] not in VALID_DOMAINS:
        return f"domain must be one of {VALID_DOMAINS}, got {data['domain']!r}"
    if data["difficulty_hint"] not in VALID_DIFFICULTIES:
        return f"difficulty_hint must be one of {VALID_DIFFICULTIES}, got {data['difficulty_hint']!r}"
    if not isinstance(data["subtopics"], list) or not data["subtopics"]:
        return "subtopics must be a non-empty list"
    if not (4 <= len(data["subtopics"]) <= 8):
        return f"subtopics should be 4-8 entries, got {len(data['subtopics'])}"
    if not all(isinstance(s, str) for s in data["subtopics"]):
        return "every subtopic must be a string"
    if not isinstance(data["prereq_slugs"], list):
        return "prereq_slugs must be a list"
    for slug in data["prereq_slugs"]:
        if slug not in known_slugs:
            return f"unknown prereq slug: {slug!r} (must exist in megagraph or earlier YAML)"
    for slug in data.get("related_slugs", []) or []:
        if slug not in known_slugs:
            return f"unknown related slug: {slug!r}"
    return None


def _load_all(seed_dir: Path) -> list[dict[str, Any]]:
    yamls = sorted(seed_dir.glob("*.yaml"))
    parsed: list[dict[str, Any]] = []
    for p in yamls:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            sys.exit(f"ERROR: {p.name}: file must contain a single YAML mapping")
        data["__source"] = p.name
        parsed.append(data)
    return parsed


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _apply_nodes(
    sb: Client, parsed: list[dict[str, Any]], slug_to_id: dict[str, str], dry_run: bool
) -> dict[str, str]:
    """Insert new nodes; update existing ones (including reclaim of created_by_user_id).

    Returns the updated slug_to_id map so edge insertion can look up the new ids.
    """
    inserts = []
    updates = []
    for data in parsed:
        if data["slug"] in slug_to_id:
            updates.append(data)
        else:
            inserts.append(data)

    print(f"\nNodes: {len(inserts)} insert, {len(updates)} update")
    for data in inserts:
        print(f"  + {data['slug']:48} ({data['domain']:>7}, {data['difficulty_hint']})")
    for data in updates:
        print(f"  ~ {data['slug']:48} (will reclaim created_by_user_id=NULL)")

    if dry_run:
        return slug_to_id

    for data in inserts:
        row = {
            "slug": data["slug"],
            "title": data["title"],
            "description_md": data["description_md"].rstrip(),
            "domain": data["domain"],
            "kind": "interest",
            "difficulty_hint": data["difficulty_hint"],
            "subtopics_json": data["subtopics"],
            "created_by_user_id": None,
        }
        result = sb.table("nodes").insert(row).execute()
        slug_to_id[data["slug"]] = result.data[0]["id"]

    for data in updates:
        row = {
            "title": data["title"],
            "description_md": data["description_md"].rstrip(),
            "domain": data["domain"],
            "difficulty_hint": data["difficulty_hint"],
            "subtopics_json": data["subtopics"],
            "created_by_user_id": None,  # reclaim as seed
        }
        sb.table("nodes").update(row).eq("slug", data["slug"]).execute()

    return slug_to_id


def _apply_edges(
    sb: Client, parsed: list[dict[str, Any]], slug_to_id: dict[str, str], dry_run: bool
) -> None:
    """Plan + apply prereq and related edges. Edge presence is checked by
    (source_slug, target_slug, edge_kind) so dry-run can plan over nodes
    that haven't been inserted yet."""
    # Build existing-edges set keyed by slug pair (lookup ids → slugs).
    id_to_slug = {v: k for k, v in slug_to_id.items()}
    existing = sb.table("edges").select("source_node_id, target_node_id, edge_kind").execute().data
    have: set[tuple[str, str, str]] = set()
    for e in existing:
        src = id_to_slug.get(e["source_node_id"])
        tgt = id_to_slug.get(e["target_node_id"])
        if src and tgt:
            have.add((src, tgt, e["edge_kind"]))

    planned: list[tuple[str, str, str]] = []  # (src_slug, tgt_slug, edge_kind)
    seen_in_plan: set[tuple[str, str, str]] = set()
    for data in parsed:
        target_slug = data["slug"]
        for prereq_slug in data["prereq_slugs"]:
            key = (prereq_slug, target_slug, "prerequisite")
            if key in have or key in seen_in_plan:
                continue
            planned.append(key)
            seen_in_plan.add(key)
        for related_slug in data.get("related_slugs", []) or []:
            if related_slug == target_slug:
                continue
            key = (related_slug, target_slug, "related")
            if key in have or key in seen_in_plan:
                continue
            planned.append(key)
            seen_in_plan.add(key)

    print(f"\nEdges: {len(planned)} new")
    for src_slug, tgt_slug, edge_kind in planned:
        print(f"  + {src_slug:35} -> {tgt_slug:35} ({edge_kind})")

    if dry_run:
        return

    # Insert one row at a time — see the Step 9b fix in add_interest.py for
    # why batching here is unsafe.
    for src_slug, tgt_slug, edge_kind in planned:
        src_id = slug_to_id.get(src_slug)
        tgt_id = slug_to_id.get(tgt_slug)
        if not src_id or not tgt_id:
            print(f"  ! skipping ({src_slug} -> {tgt_slug}): missing id post-insert")
            continue
        row = {"source_node_id": src_id, "target_node_id": tgt_id, "edge_kind": edge_kind}
        try:
            sb.table("edges").insert(row).execute()
        except Exception as exc:
            msg = str(exc)
            if "23505" in msg or "duplicate" in msg.lower():
                # Race or seed-rerun — safe to skip.
                continue
            raise


def _plan_with_pending_slugs(
    parsed: list[dict[str, Any]], existing_slugs: set[str]
) -> str | None:
    """Validate every YAML against the union of (existing slugs in DB) and
    (every slug declared in this batch). Order-independent — a YAML can
    reference any other YAML in the batch as a prereq or related slug.
    Also catches duplicate slug declarations within the batch."""
    batch_slugs: list[str] = []
    seen_in_batch: set[str] = set()
    for data in parsed:
        slug = data.get("slug")
        if not slug:
            return f"{data.get('__source', '?')}: missing slug"
        if slug in seen_in_batch:
            return f"{data['__source']}: slug {slug!r} declared twice in this batch"
        seen_in_batch.add(slug)
        batch_slugs.append(slug)

    known: set[str] = set(existing_slugs) | seen_in_batch
    for data in parsed:
        err = _validate(data, known)
        if err:
            return f"{data.get('__source', data.get('slug', '?'))}: {err}"
    return None


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_apply(dry_run: bool) -> None:
    sb = _get_supabase()
    parsed = _load_all(SEED_DIR)
    if not parsed:
        print(f"No YAML files under {SEED_DIR}")
        return

    nodes_resp = sb.table("nodes").select("id, slug").execute()
    slug_to_id = {n["slug"]: n["id"] for n in nodes_resp.data or []}
    existing_slugs = set(slug_to_id)

    err = _plan_with_pending_slugs(parsed, existing_slugs)
    if err:
        sys.exit(f"ERROR: {err}")

    print(f"Loaded {len(parsed)} seed file(s) from {SEED_DIR}")
    print(f"Existing megagraph nodes: {len(existing_slugs)}")
    if dry_run:
        print("(dry-run — no DB writes)")

    slug_to_id = _apply_nodes(sb, parsed, slug_to_id, dry_run)
    _apply_edges(sb, parsed, slug_to_id, dry_run)

    if dry_run:
        print("\nDone (dry-run). Re-run with --apply to write.")
    else:
        print("\nDone.")


def cmd_reclaim(slug: str) -> None:
    sb = _get_supabase()
    existing = sb.table("nodes").select("id, slug, created_by_user_id").eq("slug", slug).execute().data
    if not existing:
        sys.exit(f"ERROR: no node with slug {slug!r}")
    row = existing[0]
    if row["created_by_user_id"] is None:
        print(f"{slug}: already reclaimed (created_by_user_id is NULL)")
        return
    sb.table("nodes").update({"created_by_user_id": None}).eq("id", row["id"]).execute()
    print(f"{slug}: created_by_user_id set to NULL (was {row['created_by_user_id']})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="show plan without writing")
    group.add_argument("--apply", action="store_true", help="apply all YAMLs to the DB")
    group.add_argument("--reclaim-slug", metavar="SLUG", help="set created_by_user_id=NULL on an existing node")
    args = p.parse_args()

    if args.reclaim_slug:
        cmd_reclaim(args.reclaim_slug)
    else:
        cmd_apply(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
