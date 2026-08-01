"use client";

import { useEffect, useState } from "react";
import Topbar from "@/components/topbar";
import VisionPanel from "@/components/vision-panel";
import { getVisionObjectsFastAnnotated, getVisionSummaryFast } from "@/lib/api";

type Annotated = { annotated_image?: string; objects?: unknown[] };

export default function VisionPage() {
  const [summary, setSummary] = useState<string>("");
  const [annotated, setAnnotated] = useState<Annotated | null>(null);
  const [failed, setFailed] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [s, a] = await Promise.all([
          getVisionSummaryFast(),
          getVisionObjectsFastAnnotated(),
        ]);
        if (cancelled) return;
        setSummary((s as { summary?: string })?.summary ?? "");
        setAnnotated(a as Annotated);
      } catch (err) {
        console.error(err);
        if (!cancelled) setFailed(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      <Topbar
        title="Vision"
        subtitle="SAM segments the current camera frame, CLIP labels the masks. Detection runs on CPU, so a frame takes a few seconds."
      />

      {failed ? (
        <p
          role="alert"
          className="mb-6 border-l-2 border-signal py-1 pl-3 text-[13px] text-signal"
        >
          Vision service unavailable — it needs the SAM checkpoint and a live camera feed.
        </p>
      ) : null}

      {loading ? (
        <p className="font-data text-[12px] text-muted">reading the current frame…</p>
      ) : (
        <VisionPanel
          summary={summary}
          annotatedImage={annotated?.annotated_image}
          objects={(annotated?.objects as never[]) || []}
        />
      )}
    </div>
  );
}
