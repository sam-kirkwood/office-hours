import type { Metadata } from "next";
import { Inter, Source_Serif_4, Lora, JetBrains_Mono } from "next/font/google";
import Link from "next/link";
import { Toaster } from "sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${sourceSerif4.variable} ${lora.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <TooltipProvider>
          <Toaster position="bottom-right" closeButton />
          <nav className="border-b border-border bg-background">
            <div className="mx-auto flex max-w-2xl items-center gap-6 px-4 py-3">
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
