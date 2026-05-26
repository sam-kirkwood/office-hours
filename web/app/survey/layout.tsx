import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import SurveyProgress from "@/components/survey/SurveyProgress";
import RestartSurveyButton from "@/components/survey/RestartSurveyButton";

export default async function SurveyLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/signin");

  const isAdmin = !!process.env.ADMIN_EMAIL && user.email === process.env.ADMIN_EMAIL;

  return (
    <main className="min-h-screen bg-background">
      <header className="border-b border-border bg-card/40">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-3">
          <span className="font-serif text-sm text-foreground">Office Hours</span>
          <div className="flex items-center gap-3">
            <SurveyProgress />
            {isAdmin && <RestartSurveyButton />}
          </div>
        </div>
      </header>
      {children}
    </main>
  );
}
