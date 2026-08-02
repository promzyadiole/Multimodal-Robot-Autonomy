"use client";

import { useEffect, useMemo, useState } from "react";
import Topbar from "@/components/topbar";
import {
  getCommandGraph,
  sendGraphCommand,
  type CommandGraphData,
  type GraphRunData,
} from "@/lib/api";

/* ------------------------------------------------------------------ *
   The graph is drawn rather than rendered from the mermaid string, so
   that a run can light up the exact route it took. The layout mirrors
   CommandGraph._build() in the backend; the node ids are the same
   strings that come back in `path`, which is what drives the
   highlighting.
 * ------------------------------------------------------------------ */

type NodeId = "understand" | "navigate" | "verify" | "recover" | "move" | "answer";

const NODE_W = 132;
const NODE_H = 36;

const LAYOUT: Record<NodeId, { x: number; y: number; label: string; sub: string }> = {
  understand: { x: 320, y: 96, label: "understand", sub: "classify intent" },
  navigate: { x: 150, y: 200, label: "navigate", sub: "resolve pose, dispatch" },
  verify: { x: 150, y: 284, label: "verify", sub: "await real outcome" },
  recover: { x: 150, y: 368, label: "recover", sub: "clear costmaps" },
  move: { x: 496, y: 200, label: "move", sub: "velocity primitive" },
  answer: { x: 320, y: 452, label: "answer", sub: "reply with the reason" },
};

type Edge = {
  from: NodeId | "START";
  to: NodeId | "DONE";
  d: string;
  label?: string;
  /** where the label sits */
  lx?: number;
  ly?: number;
  /** degrees, for labels that run along a vertical segment */
  rotate?: number;
};

const EDGES: Edge[] = [
  { from: "START", to: "understand", d: "M320 52 L320 76" },
  {
    from: "understand",
    to: "navigate",
    d: "M283 114 L188 180",
    label: "names a place",
    lx: 175,
    ly: 146,
  },
  {
    from: "understand",
    to: "move",
    d: "M357 114 L458 180",
    label: "raw motion",
    lx: 466,
    ly: 146,
  },
  {
    from: "understand",
    to: "answer",
    d: "M320 116 L320 432",
    label: "a question",
    lx: 330,
    ly: 274,
  },
  { from: "navigate", to: "verify", d: "M150 220 L150 262" },
  {
    from: "verify",
    to: "recover",
    d: "M150 304 L150 346",
    label: "aborted",
    lx: 160,
    ly: 328,
  },
  {
    from: "verify",
    to: "answer",
    d: "M216 290 Q280 300 274 432",
    label: "succeeded",
    lx: 232,
    ly: 348,
  },
  {
    // routed wide of the column so the label does not sit on the verify box
    from: "recover",
    to: "navigate",
    d: "M84 368 L38 368 L38 200 L82 200",
    label: "retry once",
    lx: 26,
    ly: 284,
    rotate: -90,
  },
  { from: "move", to: "answer", d: "M496 220 Q496 400 388 442" },
  { from: "answer", to: "DONE", d: "M320 472 L320 494" },
];

/** Which edges a run traversed, from the ordered node trail. */
function traversedEdges(path: string[]): Set<string> {
  const taken = new Set<string>();
  if (path.length === 0) return taken;
  taken.add(`START->${path[0]}`);
  for (let i = 0; i < path.length - 1; i += 1) {
    taken.add(`${path[i]}->${path[i + 1]}`);
  }
  taken.add(`${path[path.length - 1]}->DONE`);
  return taken;
}

export default function GraphPage() {
  const [shape, setShape] = useState<CommandGraphData | null>(null);
  const [command, setCommand] = useState<string>("go to the garage");
  const [run, setRun] = useState<GraphRunData | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    getCommandGraph()
      .then((r) => setShape(r.data ?? null))
      .catch(() => setShape(null));
  }, []);

  const path = useMemo(() => (run?.path ?? []) as string[], [run]);
  const visited = useMemo(() => new Set(path), [path]);
  const taken = useMemo(() => traversedEdges(path), [path]);

  const describes = useMemo(() => {
    const m: Record<string, string> = {};
    for (const n of shape?.nodes ?? []) m[n.id] = n.does;
    return m;
  }, [shape]);

  async function execute() {
    if (!command.trim()) return;
    setBusy(true);
    setError("");
    setRun(null);
    try {
      const res = await sendGraphCommand(command.trim());
      setRun(res.data ?? null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "The command failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <Topbar
        title="Reasoning"
        subtitle="The LangGraph state machine every command runs through, and the route a run actually took. Nodes light up in the order they executed."
      />

      <section className="mb-6 grid gap-px overflow-hidden rounded-sm border border-rule bg-rule sm:grid-cols-3">
        <Readout label="graph" value={`${shape?.nodes?.length ?? "—"} nodes`} />
        <Readout
          label="langsmith tracing"
          value={shape?.tracing_enabled ? "on" : "off"}
          tone={shape?.tracing_enabled ? "good" : "muted"}
        />
        <Readout label="project" value={shape?.langsmith_project ?? "—"} />
      </section>

      {/* Run bar */}
      <div className="mb-6 flex flex-col gap-2 sm:flex-row">
        <input
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !busy) execute();
          }}
          placeholder="type a command to run through the graph"
          className="flex-1 rounded-sm border border-rule bg-ground px-4 py-3 font-data text-[13px] text-ink placeholder:text-muted focus:border-scan focus:outline-none"
        />
        <button
          type="button"
          onClick={execute}
          disabled={busy}
          className="rounded-sm bg-scan px-6 py-3 font-data text-[13px] font-medium text-ground transition-colors hover:bg-scan-hot disabled:cursor-not-allowed disabled:bg-panel-2 disabled:text-muted"
        >
          {busy ? "running…" : "run through graph"}
        </button>
      </div>

      {busy ? (
        <p className="mb-4 border-l-2 border-scan py-1 pl-3 font-data text-[12px] text-ink-soft">
          waiting for nav2&apos;s real outcome — a navigation command can take
          minutes, and the graph retries once before giving up
        </p>
      ) : null}
      {error ? (
        <p className="mb-4 border-l-2 border-signal py-1 pl-3 text-[12.5px] text-signal">
          {error}
        </p>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[1fr_23rem]">
        {/* ---- the graph ---- */}
        <section className="self-start rounded-sm border border-rule bg-panel p-4">
          {/* The diagram sits on its own inset surface. Drawing it straight onto
              the panel left the nodes almost the same value as their background;
              and it is width-capped so it does not balloon on a wide display. */}
          <div className="graph-canvas overflow-x-auto rounded-sm border border-rule bg-ground px-4 py-6">
            <svg
              viewBox="0 0 640 520"
              className="mx-auto h-auto w-full max-w-[760px] min-w-[560px]"
              role="img"
              aria-label="LangGraph command graph"
            >
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-hairline)" />
              </marker>
              <marker
                id="arrow-hot"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--color-scan)" />
              </marker>
            </defs>

            {/* terminals */}
            <Terminal x={320} y={34} text="command" active={path.length > 0} />
            <Terminal x={320} y={506} text="reply" active={path.length > 0} />

            {/* edges first, so nodes sit on top */}
            {EDGES.map((e) => {
              const hot = taken.has(`${e.from}->${e.to}`);
              return (
                <g key={`${e.from}->${e.to}`}>
                  <path
                    d={e.d}
                    fill="none"
                    stroke={hot ? "var(--color-scan)" : "var(--color-hairline)"}
                    strokeWidth={hot ? 2.25 : 1.5}
                    markerEnd={hot ? "url(#arrow-hot)" : "url(#arrow)"}
                  />
                  {e.label ? (
                    <text
                      x={e.lx}
                      y={e.ly}
                      textAnchor="middle"
                      className="font-data"
                      fontSize="10"
                      transform={e.rotate ? `rotate(${e.rotate} ${e.lx} ${e.ly})` : undefined}
                      fill={hot ? "var(--color-scan)" : "var(--color-ink-soft)"}
                    >
                      {e.label}
                    </text>
                  ) : null}
                </g>
              );
            })}

            {/* nodes */}
            {(Object.keys(LAYOUT) as NodeId[]).map((id) => {
              const n = LAYOUT[id];
              const on = visited.has(id);
              const times = path.filter((p) => p === id).length;
              return (
                <g key={id}>
                  <rect
                    x={n.x - NODE_W / 2}
                    y={n.y - NODE_H / 2}
                    width={NODE_W}
                    height={NODE_H + 14}
                    rx="3"
                    fill={on ? "var(--color-node-on)" : "var(--color-node)"}
                    stroke={on ? "var(--color-scan)" : "var(--color-hairline)"}
                    strokeWidth={on ? 1.75 : 1.25}
                  />
                  {/* a left rail marks a node the run passed through, so the
                      route reads even for a viewer who cannot separate the hues */}
                  {on ? (
                    <rect
                      x={n.x - NODE_W / 2}
                      y={n.y - NODE_H / 2}
                      width="2.5"
                      height={NODE_H + 14}
                      fill="var(--color-scan)"
                    />
                  ) : null}
                  <text
                    x={n.x}
                    y={n.y + 1}
                    textAnchor="middle"
                    className="font-data"
                    fontSize="12"
                    fill={on ? "var(--color-ink)" : "var(--color-ink-soft)"}
                  >
                    {n.label}
                  </text>
                  <text
                    x={n.x}
                    y={n.y + 15}
                    textAnchor="middle"
                    className="font-data"
                    fontSize="9"
                    fill={on ? "var(--color-ink-soft)" : "var(--color-muted)"}
                  >
                    {n.sub}
                  </text>
                  {times > 1 ? (
                    <text
                      x={n.x + NODE_W / 2 - 10}
                      y={n.y - NODE_H / 2 + 12}
                      textAnchor="middle"
                      className="font-data"
                      fontSize="9"
                      fill="var(--color-signal)"
                    >
                      ×{times}
                    </text>
                  ) : null}
                </g>
              );
            })}
            </svg>
          </div>

          {path.length > 0 ? (
            <p className="mt-4 border-t border-rule pt-3 font-data text-[11px] leading-relaxed text-muted">
              route taken:{" "}
              <span className="text-scan">{path.join(" → ")}</span>
            </p>
          ) : (
            <p className="mt-4 flex items-center gap-2 border-t border-rule pt-3 font-data text-[11px] text-muted">
              <span
                className="inline-block h-2.5 w-2.5 shrink-0 rounded-[2px] border border-scan bg-node-on"
                aria-hidden="true"
              />
              nodes and edges light up in this colour along the route a run took
            </p>
          )}
        </section>

        {/* ---- the trace ---- */}
        <aside className="flex flex-col gap-4">
          <div className="rounded-sm border border-rule bg-panel p-4">
            <h3 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
              Trace
            </h3>

            {run ? (
              <>
                <dl className="mt-3 flex flex-col gap-1.5 font-data text-[11.5px]">
                  <Field k="intent" v={run.intent ?? "—"} />
                  <Field k="route" v={run.route ?? "—"} />
                  {run.place ? <Field k="place" v={run.place} /> : null}
                  {run.outcome ? (
                    <Field
                      k="outcome"
                      v={run.outcome}
                      tone={run.outcome === "succeeded" ? "good" : "warn"}
                    />
                  ) : null}
                  <Field k="attempts" v={String(run.attempts ?? 0)} />
                  <Field
                    k="elapsed"
                    v={
                      typeof run.elapsed_ms === "number"
                        ? `${(run.elapsed_ms / 1000).toFixed(2)} s`
                        : "—"
                    }
                  />
                </dl>

                <ol className="mt-4 flex flex-col border-t border-rule pt-3">
                  {(run.trace as TraceStep[] | undefined)?.map((s, i) => (
                    <li key={`${s.node}-${i}`} className="border-l-2 border-scan/40 pb-3 pl-3">
                      <div className="flex items-baseline gap-2">
                        <span className="font-data text-[12px] text-ink">{s.node}</span>
                        <span className="ml-auto font-data text-[10px] tabular-nums text-muted">
                          +{(s.at_ms / 1000).toFixed(2)}s · {s.took_ms}ms
                        </span>
                      </div>
                      {describes[s.node] ? (
                        <p className="mt-0.5 text-[11px] leading-snug text-muted">
                          {describes[s.node]}
                        </p>
                      ) : null}
                      <dl className="mt-1.5 flex flex-col gap-0.5">
                        {Object.entries(s.detail ?? {}).map(([k, v]) => (
                          <div key={k} className="flex gap-2 font-data text-[10.5px]">
                            <dt className="shrink-0 text-muted">{k}</dt>
                            <dd className="break-words text-ink-soft">{String(v)}</dd>
                          </div>
                        ))}
                      </dl>
                    </li>
                  ))}
                </ol>

                {run.answer ? (
                  <p className="mt-1 border-t border-rule pt-3 text-[12.5px] leading-relaxed text-ink-soft">
                    {run.answer}
                  </p>
                ) : null}
              </>
            ) : (
              <p className="mt-3 font-data text-[12px] text-muted">
                no run yet
              </p>
            )}
          </div>

          <div className="rounded-sm border border-rule bg-panel p-4">
            <h3 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
              What each node does
            </h3>
            <dl className="mt-3 flex flex-col gap-2">
              {(shape?.nodes ?? []).map((n) => (
                <div key={n.id}>
                  <dt className="font-data text-[11.5px] text-ink">{n.id}</dt>
                  <dd className="text-[11.5px] leading-snug text-muted">{n.does}</dd>
                </div>
              ))}
            </dl>
          </div>
        </aside>
      </div>
    </div>
  );
}

type TraceStep = {
  node: string;
  at_ms: number;
  took_ms: number;
  detail?: Record<string, unknown>;
};

/** The rounded START / END terminals of the graph. */
function Terminal({
  x,
  y,
  text,
  active,
}: {
  x: number;
  y: number;
  text: string;
  active: boolean;
}) {
  const w = 92;
  const h = 24;
  return (
    <g>
      <rect
        x={x - w / 2}
        y={y - h / 2}
        width={w}
        height={h}
        rx={h / 2}
        fill={active ? "var(--color-scan)" : "var(--color-node)"}
        stroke={active ? "var(--color-scan)" : "var(--color-hairline)"}
        strokeWidth="1.25"
      />
      <text
        x={x}
        y={y + 4}
        textAnchor="middle"
        className="font-data"
        fontSize="10.5"
        fill={active ? "var(--color-ground)" : "var(--color-ink-soft)"}
      >
        {text}
      </text>
    </g>
  );
}

function Readout({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "good" | "muted";
}) {
  return (
    <div className="bg-panel px-5 py-4">
      <p className="font-data text-[10px] tracking-[0.18em] text-muted uppercase">
        {label}
      </p>
      <p
        className={`mt-1.5 truncate font-data text-[14px] ${
          tone === "good" ? "text-scan" : "text-ink"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

function Field({
  k,
  v,
  tone,
}: {
  k: string;
  v: string;
  tone?: "good" | "warn";
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <dt className="text-muted">{k}</dt>
      <dd
        className={
          tone === "good" ? "text-scan" : tone === "warn" ? "text-signal" : "text-ink"
        }
      >
        {v}
      </dd>
    </div>
  );
}
