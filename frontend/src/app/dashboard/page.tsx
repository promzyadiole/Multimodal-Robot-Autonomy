"use client";

import { useEffect, useState } from "react";
import Topbar from "@/components/topbar";
import StatusCard from "@/components/status-card";
import { getHealth, getRobotStatus } from "@/lib/api";

type Status = {
  nav2_ready?: boolean;
  is_navigating?: boolean;
  current_pose?: { x: number; y: number; yaw: number; frame_id: string } | null;
  linear_velocity?: number | null;
  angular_velocity?: number | null;
};

export default function DashboardPage() {
  const [health, setHealth] = useState<unknown>(null);
  const [status, setStatus] = useState<Status | null>(null);
  const [reachable, setReachable] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [healthData, statusData] = await Promise.all([
          getHealth(),
          getRobotStatus(),
        ]);
        if (cancelled) return;
        setHealth(healthData);
        setStatus(statusData as unknown as Status);
        setReachable(true);
      } catch {
        if (!cancelled) setReachable(false);
      }
    };
    load();
    const id = setInterval(load, 2000);   // telemetry should move
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  const pose = status?.current_pose ?? null;
  const fmt = (v: number | null | undefined, digits = 3) =>
    typeof v === "number" ? v.toFixed(digits) : "—";

  return (
    <div>
      <Topbar
        title="Dashboard"
        subtitle="Live telemetry, polled every two seconds. Values come straight from the ROS bridge."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <StatusCard
          title="backend"
          value={reachable === null ? "…" : reachable && health ? "online" : "offline"}
          tone={reachable && health ? "good" : "warn"}
          description="FastAPI on :8000"
        />
        <StatusCard
          title="nav2"
          value={status ? (status.nav2_ready ? "ready" : "offline") : "…"}
          tone={status?.nav2_ready ? "good" : "warn"}
          description="from live bond heartbeats"
        />
        <StatusCard
          title="navigating"
          value={status ? (status.is_navigating ? "yes" : "idle") : "…"}
          tone={status?.is_navigating ? "good" : "neutral"}
          description="a goal is in flight"
        />
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <section className="rounded-sm border border-rule bg-panel p-5">
          <h3 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
            Pose
          </h3>
          <dl className="mt-4 flex flex-col gap-2.5 font-data text-[13px] tabular-nums">
            <Row k="x" v={fmt(pose?.x)} />
            <Row k="y" v={fmt(pose?.y)} />
            <Row k="yaw" v={pose ? `${fmt(pose.yaw)} rad` : "—"} />
            <Row k="frame" v={pose?.frame_id ?? "—"} />
          </dl>
        </section>

        <section className="rounded-sm border border-rule bg-panel p-5">
          <h3 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
            Velocity
          </h3>
          <dl className="mt-4 flex flex-col gap-2.5 font-data text-[13px] tabular-nums">
            <Row k="linear" v={`${fmt(status?.linear_velocity)} m/s`} />
            <Row k="angular" v={`${fmt(status?.angular_velocity)} rad/s`} />
          </dl>
          <p className="mt-5 text-[12px] leading-relaxed text-muted">
            Odometry is dead-reckoned from the wheels, so it cannot report a tip:
            z and roll are synthesised in 2-D.
          </p>
        </section>
      </div>

      <details className="mt-8 rounded-sm border border-rule bg-panel">
        <summary className="cursor-pointer px-5 py-3.5 font-data text-[11px] tracking-[0.2em] text-muted uppercase">
          Raw status
        </summary>
        <pre className="overflow-x-auto border-t border-rule px-5 py-4 font-data text-[12px] leading-relaxed text-ink-soft">
          {JSON.stringify(status, null, 2)}
        </pre>
      </details>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule pb-2 last:border-0 last:pb-0">
      <dt className="text-muted">{k}</dt>
      <dd className="text-ink">{v}</dd>
    </div>
  );
}
