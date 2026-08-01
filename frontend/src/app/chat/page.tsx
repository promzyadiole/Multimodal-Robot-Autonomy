"use client";

import { useState } from "react";
import Topbar from "@/components/topbar";
import ChatPanel from "@/components/chat-panel";
import { sendChatCommand } from "@/lib/api";

export default function ChatPage() {
  const [answer, setAnswer] = useState("");
  const [response, setResponse] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSendCommand(message: string) {
    try {
      setLoading(true);
      setError("");
      const result = await sendChatCommand(message);
      setResponse(JSON.stringify(result, null, 2));
      setAnswer(result?.data?.answer ?? result?.message ?? "Command processed.");
    } catch (err) {
      console.error(err);
      setError("Could not reach the backend on :8000.");
      setAnswer("");
      setResponse("");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <Topbar
        title="Chat"
        subtitle="Say where the robot should go in ordinary words. The intent is parsed, resolved against the place registry, and dispatched to nav2."
      />

      <ChatPanel onSendCommand={handleSendCommand} loading={loading} />

      {error ? (
        <p
          role="alert"
          className="mt-6 border-l-2 border-signal py-1 pl-3 text-[13px] text-signal"
        >
          {error}
        </p>
      ) : null}

      <section className="mt-8">
        <h3 className="font-data text-[11px] tracking-[0.2em] text-muted uppercase">
          Answer
        </h3>
        <p className="mt-3 border-l-2 border-scan py-1 pl-4 text-[15px] leading-relaxed text-ink">
          {answer || <span className="text-muted">nothing sent yet</span>}
        </p>
      </section>

      <details className="mt-8 rounded-sm border border-rule bg-panel">
        <summary className="cursor-pointer px-5 py-3.5 font-data text-[11px] tracking-[0.2em] text-muted uppercase">
          Raw response
        </summary>
        <pre className="overflow-x-auto border-t border-rule px-5 py-4 font-data text-[12px] leading-relaxed text-ink-soft">
          {response || "—"}
        </pre>
      </details>
    </div>
  );
}
