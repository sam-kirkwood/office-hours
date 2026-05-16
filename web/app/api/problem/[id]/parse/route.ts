import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import { parseSolution } from "@/lib/pythonApi";

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

  const { attempt_id, image_paths } = await request.json();
  if (!attempt_id || !Array.isArray(image_paths)) {
    return NextResponse.json({ error: "attempt_id and image_paths required" }, { status: 400 });
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

  // Sign each storage path so Python can read them for vision
  const signedUrls: string[] = [];
  for (const path of image_paths as string[]) {
    const { data, error } = await adminClient.storage
      .from("solutions")
      .createSignedUrl(path, 300);
    if (error || !data?.signedUrl) {
      return NextResponse.json({ error: `Failed to sign path: ${path}` }, { status: 500 });
    }
    signedUrls.push(data.signedUrl);
  }

  // Persist image paths on the attempt before calling Python
  await adminClient
    .from("attempts")
    .update({ raw_image_paths: image_paths })
    .eq("id", attempt_id);

  const result = await parseSolution({
    userId: user.id,
    attemptId: attempt_id,
    imageUrls: signedUrls,
  });

  return NextResponse.json({
    parsed_markdown: result.parsed_markdown,
    parse_status: result.parse_status,
  });
}
