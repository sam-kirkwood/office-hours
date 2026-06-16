"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/admin/curation", label: "Curation" },
  { href: "/admin/megagraph", label: "Megagraph" },
  { href: "/admin/costs", label: "Costs" },
  { href: "/admin/users", label: "Users" },
  { href: "/admin/feedback", label: "Feedback" },
];

interface Props {
  operatorEmail: string;
}

export default function AdminNav({ operatorEmail }: Props) {
  const pathname = usePathname();

  return (
    <nav className="border-b border-border bg-background">
      <div className="flex items-center justify-between px-6 py-3">
        <div className="flex items-center gap-6">
          {LINKS.map(({ href, label }) => {
            const isActive = pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                className={[
                  "text-xs font-semibold uppercase tracking-widest transition-colors duration-[var(--duration-fast)]",
                  isActive
                    ? "border-b-2 border-primary pb-0.5 text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                ].join(" ")}
              >
                {label}
              </Link>
            );
          })}
        </div>
        <span className="text-xs text-muted-foreground">{operatorEmail}</span>
      </div>
    </nav>
  );
}
