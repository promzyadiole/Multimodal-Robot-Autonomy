"use client";

import { usePathname } from "next/navigation";
import Sidebar from "@/components/sidebar";

/**
 * The landing page is the entry point and runs full-bleed; every other
 * route keeps the console shell with its sidebar. Deciding here rather
 * than in the root layout avoids moving the existing routes into a
 * route group.
 */
export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/") {
    return <>{children}</>;
  }

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-[1600px]">
      <aside className="w-64 shrink-0 border-r border-rule bg-panel">
        <Sidebar />
      </aside>
      <main className="min-w-0 flex-1 overflow-x-auto p-4 md:p-6">
        <div className="mx-auto w-full max-w-6xl">{children}</div>
      </main>
    </div>
  );
}
