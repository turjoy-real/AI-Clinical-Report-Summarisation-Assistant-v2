// Follow-up chat — enabled only after the run is finalized (post-approval).

import { useState } from "react";
import { sendChat } from "../api";
import type { ChatMessage, RunRecord } from "../types";

export default function ChatPanel({
  run,
  onHistory,
}: {
  run: RunRecord;
  onHistory: (history: ChatMessage[]) => void;
}) {
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const enabled = run.status === "finalized";

  async function handleSend() {
    const text = message.trim();
    if (!text || sending || !enabled) return;
    setSending(true);
    setError(null);
    try {
      const result = await sendChat(run.run_id, text);
      setMessage("");
      onHistory(result.chat_history);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chat failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <section aria-label="Follow-up chat" className="rounded-md border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-900">Follow-up chat</h3>
      {!enabled && (
        <p className="mt-2 text-sm text-slate-500" data-testid="chat-disabled">
          Available after approval.
        </p>
      )}
      {enabled && (
        <>
          {run.chat_history.length > 0 && (
            <ul className="mt-3 max-h-64 space-y-2 overflow-y-auto" aria-label="Chat history">
              {run.chat_history.map((msg, index) => (
                <li
                  key={`${msg.timestamp}-${index}`}
                  className={`rounded-md px-3 py-2 text-sm ${
                    msg.role === "user" ? "ml-8 bg-sky-50 text-slate-800" : "mr-8 bg-slate-50 text-slate-800"
                  }`}
                >
                  <span className="block text-xs font-medium text-slate-400">
                    {msg.role === "user" ? "You" : "Assistant"}
                  </span>
                  {msg.content}
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex gap-2">
            <label htmlFor="chat-input" className="sr-only">
              Ask a follow-up question about the approved draft
            </label>
            <input
              id="chat-input"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") handleSend();
              }}
              placeholder="Ask about the approved draft…"
              className="flex-1 rounded border border-slate-300 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none"
              disabled={sending}
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={sending || !message.trim()}
              className="rounded bg-sky-600 px-4 py-2 text-sm font-medium text-white hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {sending ? "Sending…" : "Send"}
            </button>
          </div>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
        </>
      )}
    </section>
  );
}
