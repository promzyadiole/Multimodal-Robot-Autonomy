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
    <div className="flex min-h-screen flex-col bg-panel">
      <Link href="/" className="block border-b border-rule px-5 py-5">
        <span className="font-data text-[10px] tracking-[0.22em] text-muted uppercase">
          Command centre
        </span>
        <h1 className="mt-1.5 font-display text-[1.45rem] leading-none text-ink">
          ROMR
        </h1>
      </Link>

      {/* The chrome itself reports whether anything is actually running. */}
      <div className="flex items-center gap-2 border-b border-rule px-5 py-3 font-data text-[11px]">
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${
            online === null ? "bg-muted" : online ? "blink bg-scan" : "bg-signal"
          }`}
          aria-hidden="true"
        />
        <span className={online ? "text-scan" : "text-muted"}>
          {online === null ? "checking…" : online ? "nav2 ready" : "nav2 offline"}
        </span>
      </div>

      <nav className="flex-1 px-3 py-5">
        {groups.map((group) => (
          <div key={group.label} className="mb-6">
            <p className="px-2 pb-2 font-data text-[10px] tracking-[0.2em] text-muted uppercase">
              {group.label}
            </p>
            <div className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={active ? "page" : undefined}
                    className={`group flex items-baseline gap-2 rounded-sm border-l-2 px-3 py-2.5 transition-colors ${
                      active
                        ? "border-scan bg-panel-2 text-ink"
                        : "border-transparent text-ink-soft hover:border-rule hover:text-ink"
                    }`}
                  >
                    <span className="text-[14px] leading-none">{item.label}</span>
                    <span className="ml-auto font-data text-[10px] text-muted opacity-0 transition-opacity group-hover:opacity-100">
                      {item.hint}
                    </span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-rule px-5 py-4">
        <div className="flex items-center gap-3">
          <div className="relative h-9 w-9 shrink-0 overflow-hidden rounded-full border border-rule">
            <Image src="/profile.png" alt="" fill sizes="36px" className="object-cover" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[13px] text-ink">Promise Adiole</p>
            <p className="font-data text-[10px] text-muted">CPS Leoben · ARMAC</p>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-3 rounded-sm bg-ink/95 px-3 py-2">
          <Image
            src="/logo-1.png"
            alt="Cyber-Physical Systems"
            width={70}
            height={20}
            className="h-[20px] w-auto"
          />
          <span className="h-4 w-px bg-ground/15" aria-hidden="true" />
          <Image
            src="/logo-2.png"
            alt="Université Marie et Louis Pasteur"
            width={92}
            height={20}
            className="h-[20px] w-auto"
          />
        </div>
      </div>
    </div>
  );
}
