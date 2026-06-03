import type { Metadata } from "next";
import { Inter, Source_Serif_4, Lora, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { createClient } from "@/lib/supabase/server";
import { createClient as createAdminClient } from "@supabase/supabase-js";
import "./globals.css";
import "katex/dist/katex.min.css";
import "@xyflow/react/dist/style.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const sourceSerif4 = Source_Serif_4({
  variable: "--font-source-serif-4",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
});

const lora = Lora({
  variable: "--font-lora",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Science Tutor",
  description: "Personalized science tutor for friends",
};

async function getRecentNotebookCount(): Promise<number> {
  // S9 — surface the notebook as a first-class destination. Show a small
  // recent-activity count on the nav link so users can tell at a glance whether
  // there's something new to revisit. Past 7 days; 0 → link reads plain.
  try {
    const supabase = await createClient();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return 0;

    const admin = createAdminClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.SUPABASE_SECRET_KEY!,
    );
    const cutoff = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
    const { count } = await admin
      .from("notebook_entries")
      .select("id", { count: "exact", head: true })
      .eq("user_id", user.id)
      .gte("created_at", cutoff);
    return count ?? 0;
  } catch {
    return 0;
  }
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const recentNotebookCount = await getRecentNotebookCount();
  return (
    <html
      lang="en"
      className={`${inter.variable} ${sourceSerif4.variable} ${lora.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <TooltipProvider>
          <Toaster position="bottom-right" closeButton />
          <nav className="border-b border-border bg-background">
            <div className="mx-auto flex max-w-2xl items-center gap-4 px-4 py-3 sm:gap-6">
              <Link
                href="/daily"
                className="text-sm font-semibold text-foreground hover:text-primary transition-colors duration-[var(--duration-fast)]"
              >
                Daily
              </Link>
              <Link
                href="/notebook"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]"
              >
                Notebook
                {recentNotebookCount > 0 && (
                  <span className="ml-1 text-xs text-muted-foreground/70">
                    ({recentNotebookCount})
                  </span>
                )}
              </Link>
              <Link
                href="/skill-tree"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]"
              >
                Skill Tree
              </Link>
              <Link
                href="/profile"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors duration-[var(--duration-fast)]"
              >
                Profile
              </Link>
            </div>
          </nav>
          {children}
        </TooltipProvider>
      </body>
    </html>
  );
}
