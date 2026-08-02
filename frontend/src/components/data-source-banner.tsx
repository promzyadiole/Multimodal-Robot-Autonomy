"use client";

import { useEffect, useState } from "react";
import { isUsingRecording, onDataSourceChange } from "@/lib/api";

/**
 * Says plainly when the interface is showing a recording rather than a live
 * robot. The public deployment has no robot behind it, and a demo that does not
 * admit that is a demo that misleads.
 */
export default function DataSourceBanner() {
  const [recorded, setRecorded] = useState(false);

  useEffect(() => {
    setRecorded(isUsingRecording());
    return onDataSourceChange(setRecorded);
  }, []);

  if (!recorded) return null;

  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-signal/30 bg-signal/10 px-6 py-2 font-data text-[11.5px] text-signal"
    >
      <span
        className="inline-block h-1.5 w-1.5 shrink-0 rounded-full bg-signal"
        aria-hidden="true"
      />
      <span className="font-medium">recorded run</span>
      <span className="text-signal/80">
        — no robot is connected. Gazebo, ROS 2 and the perception models cannot
        run on this host, and one navigation command takes 25–143 s. Everything
        shown is measured data from a real run.
      </span>
    </div>
  );
}
