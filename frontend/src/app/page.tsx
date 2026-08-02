"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import { getEnvironment, getNavigationPlaces, getRobotStatus } from "@/lib/api";

type Live = {
  environment?: string;
  map?: string;
  places?: string[];
  nav2Ready?: boolean;
  pose?: { x: number; y: number } | null;
  reachable: boolean;
};

/** Real numbers measured in simulation — not marketing claims. */
const MEASURED = [
  { k: "scan match to map", v: "92.5%", n: "within 10 cm, median error 0.050 m" },
  { k: "robot footprint", v: "0.521 × 0.608 m", n: "modelled as a polygon, not a circle" },
  { k: "named destinations", v: "7", n: "resolved from language, not coordinates" },
  { k: "goal accuracy", v: "0.16 – 0.30 m", n: "final error across verified runs" },
];

export default function LandingPage() {
  const [live, setLive] = useState<Live>({ reachable: false });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [env, places, status] = await Promise.all([
          getEnvironment(),
          getNavigationPlaces(),
          getRobotStatus(),
        ]);
        if (cancelled) return;
        const e = env?.data as Record<string, unknown> | undefined;
        const nav = (e?.navigation ?? {}) as Record<string, string>;
        const st = status as unknown as Record<string, unknown> | undefined;
        setLive({
          reachable: true,
          environment: (e?.name as string) ?? undefined,
          map: nav?.map_yaml_path?.split("/").pop(),
          places: Object.keys(
            ((places?.data as Record<string, unknown>)?.places ?? {}) as object,
          ),
          nav2Ready: Boolean(st?.nav2_ready),
          pose: (st?.current_pose as { x: number; y: number } | null) ?? null,
        });
      } catch {
        if (!cancelled) setLive({ reachable: false });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="relative min-h-screen overflow-hidden">
      <div className="pointer-events-none absolute inset-0 grid-raster" aria-hidden="true" />

      {/* ---------------- hero ---------------- */}
      <header className="relative mx-auto max-w-[1180px] px-6 pt-14 pb-6 md:pt-20">
        <div className="scanline" aria-hidden="true" />

        <div className="rise flex flex-wrap items-center gap-3 font-data text-[11px] tracking-[0.2em] text-muted uppercase">
          <span>Personal project</span>
          <span className="text-rule">/</span>
          <span>Language-grounded autonomy</span>
          <span className="text-rule">/</span>
          <span>ROS&nbsp;2 · LangGraph</span>
        </div>

        <div className="mt-8 grid items-end gap-10 md:grid-cols-[1.35fr_0.65fr]">
          <div>
            <h1
              className="rise font-display text-[clamp(2.6rem,7vw,5.2rem)] leading-[0.95] tracking-[-0.015em]"
              style={{ animationDelay: "80ms" }}
            >
              Tell the robot
              <br />
              where to go.
              <span className="block italic text-scan">In plain language.</span>
            </h1>

            <p
              className="rise mt-7 max-w-xl text-[15px] leading-relaxed text-ink-soft"
              style={{ animationDelay: "160ms" }}
            >
              A custom differential-drive robot that turns a sentence into a destination —
              an LLM resolves the intent, CLIP and SAM read the scene, and ROS&nbsp;2 nav2
              drives it there. Then it checks whether it actually arrived, and says so when
              it did&nbsp;not.
            </p>

            <div
              className="rise mt-9 flex flex-wrap items-center gap-3"
              style={{ animationDelay: "240ms" }}
            >
              <Link
                href="/navigation"
                className="group inline-flex items-center gap-2.5 rounded-sm bg-scan px-6 py-3.5 font-data text-[13px] font-medium tracking-wide text-ground transition-colors hover:bg-scan-hot"
              >
                Try the solution
                <span
                  aria-hidden="true"
                  className="transition-transform group-hover:translate-x-1"
                >
                  →
                </span>
              </Link>
              <Link
                href="/dashboard"
                className="inline-flex items-center rounded-sm border border-rule px-6 py-3.5 font-data text-[13px] tracking-wide text-ink-soft transition-colors hover:border-scan hover:text-ink"
              >
                Live telemetry
              </Link>
            </div>
          </div>

          {/* portrait, offset so it breaks the baseline of the headline block */}
          <figure
            className="rise relative mx-auto w-full max-w-[260px] md:mx-0 md:translate-y-4"
            style={{ animationDelay: "320ms" }}
          >
            <div className="relative aspect-square overflow-hidden rounded-sm border border-rule">
              <Image
                src="/profile.png"
                alt="Promise Emeziem Adiole"
                fill
                sizes="260px"
                preload
                className="object-cover"
              />
              <div
                className="pointer-events-none absolute inset-0"
                style={{
                  background:
                    "linear-gradient(180deg, transparent 55%, rgba(11,15,20,0.85) 100%)",
                }}
                aria-hidden="true"
              />
            </div>
            <figcaption className="mt-3 font-data text-[11px] leading-relaxed text-muted">
              <span className="text-ink-soft">Promise Emeziem Adiole</span>
              <br />
              M.Sc. Advanced Robotics, Mechatronics &amp; Automatic Control
            </figcaption>
          </figure>
        </div>
      </header>

      {/* ---------------- live strip ---------------- */}
      <section className="relative mx-auto mt-10 max-w-[1180px] px-6">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-3 border-y border-rule py-4 font-data text-[12px]">
          <span className="flex items-center gap-2">
            <span
              className={`blink inline-block h-1.5 w-1.5 rounded-full ${
                live.reachable ? "bg-scan" : "bg-signal"
              }`}
              aria-hidden="true"
            />
            <span className="text-muted">
              {live.reachable ? "system online" : "system offline"}
            </span>
          </span>

          {live.reachable ? (
            <>
              <Field label="environment" value={live.environment ?? "—"} />
              <Field label="map" value={live.map ?? "—"} />
              <Field label="destinations" value={String(live.places?.length ?? 0)} />
              <Field label="nav2" value={live.nav2Ready ? "ready" : "standby"} />
              {live.pose && (
                <Field
                  label="pose"
                  value={`${live.pose.x.toFixed(2)}, ${live.pose.y.toFixed(2)}`}
                />
              )}
            </>
          ) : (
            <span className="text-muted">
              start the backend on :8000 to stream live state
            </span>
          )}
        </div>
      </section>

      {/* ---------------- the robot ---------------- */}
      <section className="relative mx-auto mt-16 max-w-[1180px] px-6">
        <h2 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
          The robot
        </h2>
        <figure className="mt-6 overflow-hidden rounded-sm border border-rule bg-panel">
          <div className="relative aspect-[21/9] w-full">
            <Image
              src="/rviz_romr.png"
              alt="ROMR rendered in RViz: the cart chassis with its lidar on top, both casters, and live laser returns in red"
              fill
              sizes="(max-width: 1180px) 100vw, 1180px"
              className="object-cover object-[50%_38%]"
            />
          </div>
          <figcaption className="border-t border-rule px-6 py-4 font-data text-[12px] leading-relaxed text-muted">
            ROMR in RViz — 0.521 × 0.608 m differential drive, lidar at 0.44 m, a
            caster at each end. The red returns are the live scan it navigates by.
          </figcaption>
        </figure>
      </section>

      {/* ---------------- destinations ---------------- */}
      <section className="relative mx-auto mt-16 max-w-[1180px] px-6">
        <h2 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
          Three ways in
        </h2>

        <div className="mt-6 grid gap-px overflow-hidden rounded-sm border border-rule bg-rule md:grid-cols-3">
          <Card
            href="/navigation"
            index="01"
            title="Test the solution"
            body="Send the robot to a named place, watch it resolve the pose, plan a route, and report whether it arrived."
            cta="Open the console"
          />
          <Card
            href="/chat"
            index="02"
            title="Talk to it"
            body="Type a destination in ordinary words. The intent is parsed, checked against the map, and dispatched."
            cta="Open chat"
          />
          <Card
            index="03"
            title="The thesis"
            body="The written work behind this system, and a retrieval layer to query its ideas directly."
            cta="In preparation"
            muted
          />
        </div>
      </section>

      {/* ---------------- measured ---------------- */}
      <section className="relative mx-auto mt-16 max-w-[1180px] px-6">
        <h2 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
          Measured, not claimed
        </h2>
        <dl className="mt-6 grid gap-x-10 gap-y-7 sm:grid-cols-2 lg:grid-cols-4">
          {MEASURED.map((m) => (
            <div key={m.k} className="border-t border-rule pt-4">
              <dt className="font-data text-[11px] tracking-wide text-muted uppercase">
                {m.k}
              </dt>
              <dd className="mt-2 font-display text-[1.9rem] leading-none text-ink tabular-nums">
                {m.v}
              </dd>
              <dd className="mt-2 text-[12.5px] leading-snug text-muted">{m.n}</dd>
            </div>
          ))}
        </dl>
      </section>

      {/* ---------------- footer ---------------- */}
      <footer className="relative mx-auto mt-20 max-w-[1180px] px-6 pb-16">
        <div className="flex flex-wrap items-center justify-between gap-6 border-t border-rule pt-8">
          <p className="max-w-lg text-[12.5px] leading-relaxed text-muted">
            A personal project by Promise Adiole. Built on ROS&nbsp;2 Humble and
            Gazebo, using ROMR, an open-source mobile robot. The findings here are
            my own and represent no institution.
          </p>
          <a
            href="https://github.com/promzyadiole/Multimodal-Robot-Autonomy"
            target="_blank"
            rel="noopener noreferrer"
            className="font-data text-[12px] text-scan transition-colors hover:text-scan-hot"
          >
            source on github →
          </a>
        </div>
      </footer>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <span className="flex items-baseline gap-2">
      <span className="text-muted">{label}</span>
      <span className="text-ink">{value}</span>
    </span>
  );
}

function Card({
  href,
  index,
  title,
  body,
  cta,
  muted = false,
}: {
  href?: string;
  index: string;
  title: string;
  body: string;
  cta: string;
  muted?: boolean;
}) {
  const inner = (
    <div className="group flex h-full flex-col bg-panel p-7 transition-colors hover:bg-panel-2">
      <span className="font-data text-[11px] tracking-[0.2em] text-scan">{index}</span>
      <h3 className="mt-5 font-display text-[1.6rem] leading-tight">{title}</h3>
      <p className="mt-3 flex-1 text-[13.5px] leading-relaxed text-ink-soft">{body}</p>
      <span
        className={`mt-6 inline-flex items-center gap-2 font-data text-[12px] ${
          muted ? "text-muted" : "text-scan"
        }`}
      >
        {cta}
        {!muted && (
          <span
            aria-hidden="true"
            className="transition-transform group-hover:translate-x-1"
          >
            →
          </span>
        )}
      </span>
    </div>
  );

  return href ? (
    <Link href={href} className="block">
      {inner}
    </Link>
  ) : (
    inner
  );
}
