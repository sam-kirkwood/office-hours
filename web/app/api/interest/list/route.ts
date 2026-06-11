import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

// GET /api/interest/list
// The caller's interests, with node slug + title. Used by the notebook to
// build its by-interest tab strip (n1). Read-only, user-scoped via RLS.

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data, error } = await supabase
    .from("user_interests")
    .select("node_id, created_at, nodes(slug, title)")
    .eq("user_id", user.id)
    .order("created_at", { ascending: true });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  const interests = (data ?? [])
    .map((row) => {
      const node = (row as { nodes?: { slug?: string; title?: string } }).nodes;
      return {
        node_id: (row as { node_id: string }).node_id,
        slug: node?.slug ?? null,
        title: node?.title ?? null,
      };
    })
    .filter((i): i is { node_id: string; slug: string; title: string } =>
      Boolean(i.slug && i.title),
    );

  return NextResponse.json({ interests });
}
