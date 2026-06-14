import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

type FeedbackKind = "easier" | "harder" | "assume_less";

const KIND_TO_COLUMN: Record<FeedbackKind, string> = {
  easier: "requested_easier",
  harder: "requested_harder",
  assume_less: "requested_assume_less",
};

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
  const { attempt_id, kind } = body as { attempt_id?: string; kind?: string };

  if (!attempt_id || !kind || !(kind in KIND_TO_COLUMN)) {
    return NextResponse.json(
      { error: "attempt_id and kind (easier|harder|assume_less) required" },
      { status: 400 },
    );
  }

  const adminClient = createAdminClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SECRET_KEY!,
  );

  const { data: attempt } = await adminClient
    .from("attempts")
    .select("id, user_id")
    .eq("id", attempt_id)
    .eq("queue_item_id", queueItemId)
    .maybeSingle();

  if (!attempt) return NextResponse.json({ error: "Not found" }, { status: 404 });
  if (attempt.user_id !== user.id) return NextResponse.json({ error: "Forbidden" }, { status: 403 });

  await adminClient
    .from("attempts")
    .update({ [KIND_TO_COLUMN[kind as FeedbackKind]]: true })
    .eq("id", attempt_id);

  return NextResponse.json({ ok: true });
}
