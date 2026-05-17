import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

export default async function RootPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/signin");

  const { data: survey } = await supabase
    .from("surveys")
    .select("id")
    .eq("user_id", user.id)
    .maybeSingle();

  if (survey) redirect("/daily");
  else redirect("/survey");
}
