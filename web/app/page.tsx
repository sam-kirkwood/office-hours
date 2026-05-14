import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export default async function RootPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/signin");

  const { data: activePlan } = await supabase
    .from("user_plans")
    .select("id")
    .eq("user_id", user.id)
    .eq("status", "active")
    .maybeSingle();

  if (activePlan) redirect("/daily");

  const { data: pendingPlan } = await supabase
    .from("user_plans")
    .select("id")
    .eq("user_id", user.id)
    .eq("status", "pending_review")
    .maybeSingle();

  if (pendingPlan) redirect("/plan");

  redirect("/survey");
}
