"use client";

import { usePathname } from "next/navigation";
import Sidebar from "@/components/sidebar";
import DataSourceBanner from "@/components/data-source-banner";

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
    // Below md the sidebar becomes a bar across the top rather than a column
    // beside the content. At 390 px a fixed 16rem rail left the page 134 px to
    // work in, which no amount of responsiveness inside the page can rescue.
    <div className="mx-auto flex min-h-screen w-full max-w-[1600px] flex-col md:flex-row">
      <aside className="w-full shrink-0 border-b border-rule bg-panel md:w-64 md:border-b-0 md:border-r">
        <Sidebar />
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <DataSourceBanner />
        <main className="min-w-0 flex-1 overflow-x-auto p-4 md:p-6">
          <div className="mx-auto w-full max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
