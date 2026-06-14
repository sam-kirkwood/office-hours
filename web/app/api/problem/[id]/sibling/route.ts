import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";
import { generateSibling, type SiblingKind } from "@/lib/pythonApi";

const VALID_KINDS = new Set<SiblingKind>(["easier", "harder", "assume_less"]);

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id: queueItemId } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await request.json().catch(() => ({}));
  const kind = body.kind as string | undefined;
  if (!kind || !VALID_KINDS.has(kind as SiblingKind)) {
    return NextResponse.json(
      { error: "kind must be one of: easier, harder, assume_less" },
      { status: 400 },
    );
  }

  const result = await generateSibling({
    userId: user.id,
    queueItemId,
    kind: kind as SiblingKind,
  });

  return NextResponse.json(result);
}
