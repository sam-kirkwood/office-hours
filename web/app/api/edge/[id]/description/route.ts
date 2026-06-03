import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { generateEdgeDescription } from "@/lib/pythonApi";

// GET /api/edge/[id]/description
//
// Proxies to the Python /generate-edge-description route. Cache-checks first
// on the server; on miss, Haiku produces a short paragraph naming the
// specific concepts that bridge from source to target, and caches it on
// edge_descriptions by edge_id. Subsequent viewers of the same edge read
// the cached row.

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: edgeId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const result = await generateEdgeDescription({
      userId: user.id,
      edgeId,
    });
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof Error ? err.message : "Failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
