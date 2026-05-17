import { NextResponse } from "next/server";
import { assertAdminApi } from "@/lib/adminAuth";
import { generateCurationReport } from "@/lib/pythonApi";

export async function POST() {
  const err = await assertAdminApi();
  if (err) return err;

  try {
    const result = await generateCurationReport();
    return NextResponse.json({ ok: true, ...result });
  } catch (e) {
    const message = e instanceof Error ? e.message : "Unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
