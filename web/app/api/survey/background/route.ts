import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { getAdminClient, upsertSurveyStage } from "@/lib/surveyState";
import {
  DOMAIN_BY_KEY,
  RELATIONSHIP_CARDS,
  type DomainKey,
  type RelationshipKey,
} from "@/lib/surveyDomains";

interface IncomingDomain {
  key?: unknown;
  subareas?: unknown;
  relationship?: unknown;
}

interface Body {
  domains: IncomingDomain[];
  short_text: string;
}

const VALID_RELATIONSHIPS = new Set<string>(RELATIONSHIP_CARDS.map((c) => c.key));

function sanitiseDomains(raw: unknown): Array<{
  key: DomainKey;
  subareas: string[];
  relationship: RelationshipKey | null;
}> {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: Array<{ key: DomainKey; subareas: string[]; relationship: RelationshipKey | null }> = [];
  for (const r of raw) {
    if (!r || typeof r !== "object") continue;
    const entry = r as IncomingDomain;
    const key = typeof entry.key === "string" ? entry.key : "";
    if (!key || seen.has(key)) continue;
    const def = DOMAIN_BY_KEY[key as DomainKey];
    if (!def) continue;
    seen.add(key);

    const validSubKeys = new Set(def.subareas.map((s) => s.key));
    const subareas = Array.isArray(entry.subareas)
      ? (entry.subareas as unknown[]).filter(
          (s): s is string => typeof s === "string" && validSubKeys.has(s),
        )
      : [];

    const rel = entry.relationship;
    const relationship =
      typeof rel === "string" && VALID_RELATIONSHIPS.has(rel)
        ? (rel as RelationshipKey)
        : null;

    out.push({ key: key as DomainKey, subareas, relationship });
  }
  return out;
}

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let body: Body;
  try {
    body = (await request.json()) as Body;
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const domains = sanitiseDomains(body.domains);
  const short_text = (body.short_text ?? "").trim();

  try {
    const admin = getAdminClient();
    await upsertSurveyStage(admin, user.id, "background", {
      background_json: { domains },
      free_text_intent: short_text,
    });
    return NextResponse.json({ ok: true });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
