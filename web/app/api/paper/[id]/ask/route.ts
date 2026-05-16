import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

const PYTHON_API_URL = process.env.PYTHON_API_URL!;
const INTERNAL_API_TOKEN = process.env.INTERNAL_API_TOKEN!;

export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  await params; // queue_item_id not needed for this route
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { engagement_id, user_message_md } = await request.json();
  if (!engagement_id || typeof user_message_md !== "string") {
    return NextResponse.json({ error: "engagement_id and user_message_md required" }, { status: 400 });
  }

  const res = await fetch(`${PYTHON_API_URL}/paper-question`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${INTERNAL_API_TOKEN}`,
    },
    body: JSON.stringify({
      user_id: user.id,
      engagement_id,
      user_message_md,
    }),
  });

  if (!res.ok) {
    const text = await res.text();
    return NextResponse.json({ error: text }, { status: res.status });
  }

  return NextResponse.json(await res.json());
}
