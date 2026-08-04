"use client";

import { useEffect, useMemo, useState } from "react";
import { getChannels, type Channel, type ChannelsData } from "@/lib/api";

/* ------------------------------------------------------------------ *
   Every route between this interface and the robot, drawn as the signal
   path it actually is: a surface in the browser, an HTTP endpoint, the
   service behind it, and the ROS topic or action on the far end.

   The inventory comes from the backend rather than being drawn here, and
   liveness is judged from traffic it has really received. That matters
   more than it sounds: the camera spent a whole session subscribed to a
   topic nobody published on, and no diagram of the system would have
   caught it, because the connection existed -- it simply carried nothing.

   The path wraps rather than scrolling. A signal path that runs off the
   side of a phone is not a diagram of anything.
 * ------------------------------------------------------------------ */

type Filter = "all" | "out" | "in" | "quiet";

export default function ChannelMap() {
  const [data, setData] = useState<ChannelsData | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [surface, setSurface] = useState<string>("all");

  useEffect(() => {
    let alive = true;
    const load = () =>
      getChannels()
        .then((r) => alive && setData(r.data ?? null))
        .catch(() => alive && setData(null));
    load();
    // Slow poll. These are connections, not telemetry -- they change when
    // something is started or dies, not continuously.
    const t = setInterval(load, 10000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);

  const channels = data?.channels ?? [];
  const surfaces = useMemo(
    () => ["all", ...(data?.surfaces ?? [])],
    [data],
  );

  const shown = channels.filter((c) => {
    if (surface !== "all" && c.surface !== surface) return false;
    if (filter === "out") return c.direction === "out";
    if (filter === "in") return c.direction === "in";
    if (filter === "quiet") return c.live !== true;
    return true;
  });

  const liveCount = channels.filter((c) => c.live === true).length;
  const quietCount = channels.filter((c) => c.live === false).length;
  const unknownCount = channels.filter((c) => c.live === null).length;

  return (
    <section className="rounded-sm border border-rule bg-panel">
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-rule px-4 py-3">
        <h3 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
          Communication channels
        </h3>
        <p className="font-data text-[11px] text-muted">
          <span className="text-scan tabular-nums">{liveCount}</span> carrying
          {quietCount > 0 ? (
            <>
              {" · "}
              <span className="text-signal tabular-nums">{quietCount}</span> silent
            </>
          ) : null}
          {unknownCount > 0 ? (
            <>
              {" · "}
              <span className="tabular-nums">{unknownCount}</span> no robot
            </>
          ) : null}
        </p>
      </header>

      {/* Filters. Both rows wrap, so they stay usable at any width. */}
      <div className="flex flex-col gap-2 border-b border-rule px-4 py-3">
        <div className="flex flex-wrap gap-1.5">
          {(
            [
              ["all", "every channel"],
              ["out", "interface → robot"],
              ["in", "robot → interface"],
              ["quiet", "not carrying"],
            ] as [Filter, string][]
          ).map(([v, label]) => (
            <button
              key={v}
              type="button"
              onClick={() => setFilter(v)}
              aria-pressed={filter === v}
              className={`rounded-sm border px-2.5 py-1 font-data text-[11px] transition-colors ${
                filter === v
                  ? "border-scan bg-node-on text-scan"
                  : "border-rule bg-ground text-muted hover:text-ink-soft"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {surfaces.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => setSurface(s)}
              aria-pressed={surface === s}
              className={`rounded-sm px-2 py-0.5 font-data text-[10.5px] transition-colors ${
                surface === s
                  ? "bg-scan text-ground"
                  : "text-muted hover:text-ink-soft"
              }`}
            >
              {s === "all" ? "all surfaces" : s}
            </button>
          ))}
        </div>
      </div>

      {data === null ? (
        <p className="px-4 py-6 font-data text-[12px] text-muted">
          loading the channel inventory…
        </p>
      ) : shown.length === 0 ? (
        <p className="px-4 py-6 font-data text-[12px] text-muted">
          nothing matches that filter
        </p>
      ) : (
        <ul className="flex flex-col">
          {shown.map((c) => (
            <ChannelRow key={c.id} c={c} />
          ))}
        </ul>
      )}

      <footer className="border-t border-rule px-4 py-3">
        <p className="font-data text-[10.5px] leading-relaxed text-muted">
          liveness is judged from traffic the backend has received, not from the
          DDS graph — <span className="text-ink-soft">count_publishers()</span>{" "}
          reported zero while nav2 was serving goals, and the action client
          claimed ready 30 s after nav2 was killed
        </p>
      </footer>
    </section>
  );
}

function ChannelRow({ c }: { c: Channel }) {
  const out = c.direction === "out";
  // The path reads in the direction the data moves, so an inbound channel is
  // written from the robot back to the surface rather than being drawn
  // outbound with a reversed arrow, which is harder to read at a glance.
  const hops = out
    ? [c.surface, c.http, c.service, c.ros]
    : [c.ros, c.service, c.http, c.surface];
  const path = hops.filter((h) => h && h !== "—");

  return (
    <li className="border-b border-rule px-4 py-3 last:border-b-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <Dot live={c.live} />
        <span className="font-data text-[12px] text-ink">{c.label}</span>
        <span
          className={`rounded-sm px-1.5 py-px font-data text-[10px] ${
            out ? "bg-node-on text-scan" : "bg-panel-2 text-ink-soft"
          }`}
        >
          {out ? "acts" : "reports"}
        </span>
        {c.ros === "—" ? (
          <span className="font-data text-[10px] text-muted">backend only</span>
        ) : null}
      </div>

      {/* The signal path. Wraps at any width rather than scrolling sideways. */}
      <div className="mt-1.5 flex flex-wrap items-center gap-x-1.5 gap-y-1">
        {path.map((hop, i) => (
          <span key={`${c.id}-${i}`} className="flex items-center gap-1.5">
            {i > 0 ? (
              <span aria-hidden="true" className="text-hairline">
                ›
              </span>
            ) : null}
            <span
              className={`font-data text-[11px] break-all ${
                i === 0 ? "text-ink-soft" : "text-muted"
              }`}
            >
              {hop}
            </span>
          </span>
        ))}
      </div>

      <p className="mt-1 text-[11px] leading-snug text-muted">{c.note}</p>
    </li>
  );
}

/** Live state as shape as well as colour, so it survives a colour-blind read. */
function Dot({ live }: { live: boolean | null }) {
  if (live === true) {
    return (
      <span
        title="carrying traffic"
        className="inline-block h-2 w-2 shrink-0 rounded-full bg-scan"
      />
    );
  }
  if (live === false) {
    return (
      <span
        title="connected but nothing has arrived"
        className="inline-block h-2 w-2 shrink-0 rounded-full border border-signal"
      />
    );
  }
  return (
    <span
      title="no ROS on this host, so the far end is unknowable"
      className="inline-block h-2 w-2 shrink-0 rounded-full border border-dashed border-muted"
    />
  );
}
