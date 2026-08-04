"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { getRobotStatus } from "@/lib/api";

// Grouped by what you are doing rather than by page order: operating the
// robot, then watching it. The landing page is reached through the title.
const groups: { label: string; items: { href: string; label: string; hint: string }[] }[] = [
  {
    label: "Operate",
    items: [
      { href: "/navigation", label: "Navigation", hint: "send it somewhere" },
      { href: "/chat", label: "Chat", hint: "ask in words" },
      { href: "/control", label: "Control", hint: "drive it directly" },
    ],
  },
  {
    label: "Observe",
    items: [
      { href: "/dashboard", label: "Dashboard", hint: "live telemetry" },
      { href: "/vision", label: "Vision", hint: "what it sees" },
      { href: "/graph", label: "Reasoning", hint: "how it decided" },
    ],
  },
];

export default function Sidebar() {
  const pathname = usePathname();
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const st = (await getRobotStatus()) as unknown as Record<string, unknown>;
        if (!cancelled) setOnline(Boolean(st?.nav2_ready));
      } catch {
        if (!cancelled) setOnline(false);
      }
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return (
    <div className="flex flex-col bg-panel md:min-h-screen">
      {/* On a phone the title and the liveness lamp share one row; as a column
          they cost two thirds of the space above the fold before a single
          navigation link. */}
      <div className="flex items-center justify-between gap-3 border-b border-rule px-4 py-3 md:block md:px-5 md:py-5">
        <Link href="/" className="block">
          <span className="font-data text-[10px] tracking-[0.22em] text-muted uppercase">
            Command centre
          </span>
          <h1 className="font-display text-[1.25rem] leading-none text-ink md:mt-1.5 md:text-[1.45rem]">
            ROMR
          </h1>
        </Link>
        <div className="flex items-center gap-2 font-data text-[11px] md:hidden">
          <Lamp online={online} />
          <span className={online ? "text-scan" : "text-muted"}>
            {online === null ? "checking…" : online ? "ready" : "offline"}
          </span>
        </div>
      </div>

      {/* The chrome itself reports whether anything is actually running. */}
      <div className="hidden items-center gap-2 border-b border-rule px-5 py-3 font-data text-[11px] md:flex">
        <Lamp online={online} />
        <span className={online ? "text-scan" : "text-muted"}>
          {online === null ? "checking…" : online ? "nav2 ready" : "nav2 offline"}
        </span>
      </div>

      {/* Horizontal and scrollable on a phone, a column from md up. The group
          headings are a wide-layout affordance and are dropped rather than
          stacked, since they would double the height of the bar. */}
      <nav className="flex gap-4 overflow-x-auto px-3 py-2 md:block md:flex-1 md:overflow-x-visible md:py-5">
        {groups.map((group) => (
          <div key={group.label} className="shrink-0 md:mb-6">
            <p className="hidden px-2 pb-2 font-data text-[10px] tracking-[0.2em] text-muted uppercase md:block">
              {group.label}
            </p>
            <div className="flex gap-1 md:flex-col md:gap-0.5">
              {group.items.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`group flex shrink-0 items-baseline gap-2 rounded-sm border-b-2 px-2.5 py-1.5 transition-colors md:border-b-0 md:border-l-2 md:px-3 md:py-2.5 ${
                      active
                        ? "border-scan bg-panel-2 text-ink"
                        : "border-transparent text-ink-soft hover:border-rule hover:text-ink"
                    }`}
                  >
                    <span className="text-[13px] leading-none md:text-[14px]">
                      {item.label}
                    </span>
                    <span className="ml-auto hidden font-data text-[10px] text-muted opacity-0 transition-opacity group-hover:opacity-100 md:inline">
                      {item.hint}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="hidden border-t border-rule px-5 py-4 md:block">
        <div className="flex items-center gap-3">
          <div className="relative h-9 w-9 shrink-0 overflow-hidden rounded-full border border-rule">
            <Image src="/profile.png" alt="" fill sizes="36px" className="object-cover" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[13px] text-ink">Promise Adiole</p>
            <p className="font-data text-[10px] text-muted">personal project</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Lamp({ online }: { online: boolean | null }) {
  return (
    <span
      className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
        online === null ? "bg-muted" : online ? "blink bg-scan" : "bg-signal"
      }`}
      aria-hidden="true"
    />
  );
}
