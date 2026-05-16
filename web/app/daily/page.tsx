import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import DailyView from "@/components/DailyView";
import { getOrSurfacePick } from "@/lib/queueHelpers";

export default async function DailyPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  // Redirect to survey if the user hasn't completed one yet.
  const { data: survey } = await supabase
    .from("surveys")
    .select("id")
    .eq("user_id", user.id)
    .limit(1)
    .maybeSingle();
  if (!survey) redirect("/survey");

  const result = await getOrSurfacePick(supabase, user.id);

  return (
    <main className="min-h-screen bg-white">
      <DailyView initialResult={result} />
    </main>
  );
}
