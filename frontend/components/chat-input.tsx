"use client";

import { useChat, useConnectionState } from "@livekit/components-react";
import { ConnectionState } from "livekit-client";
import { SendHorizontal } from "lucide-react";
import { useState } from "react";

/**
 * Typed fallback for the voice channel. The agent already listens on the
 * `lk.chat` topic — LiveKit's default text handler interrupts whatever it is
 * saying and treats the message as a user turn — so this needs no agent-side
 * change. It also means the assistant stays usable when the mic is blocked,
 * the room is noisy, or audio is simply misbehaving.
 */
export function ChatInput() {
  const { send, isSending } = useChat();
  const connection = useConnectionState();
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  // Sending is a room operation: it fails outright if the room isn't connected,
  // which the page otherwise gives no sign of — the UI renders as soon as the
  // token arrives, well before (or despite) the room connecting.
  const connected = connection === ConnectionState.Connected;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const message = text.trim();
    if (!message || isSending || !connected) return;
    setError(null);
    // Clear optimistically so the field is ready for the next line; restore it
    // if the send fails, rather than silently eating what was typed.
    setText("");
    try {
      await send(message);
    } catch (err) {
      setText(message);
      // Report what actually failed. Guessing at the cause here previously hid
      // the real error, which was the only thing that identified the problem.
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-1.5">
      <div className="flex gap-1.5">
        <label className="sr-only" htmlFor="chat-input">
          Type a message to the assistant
        </label>
        <input
          id="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={connected ? "Type instead…" : "Not connected to the room"}
          autoComplete="off"
          disabled={!connected}
          className="min-w-0 flex-1 rounded-md border border-neutral-700 bg-neutral-900 px-2.5 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400"
        />
        <button
          type="submit"
          disabled={isSending || !connected || text.trim() === ""}
          aria-label="Send message"
          className="rounded-md border border-neutral-700 px-2.5 text-neutral-300 hover:bg-neutral-800 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400"
        >
          <SendHorizontal className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-red-400">
          {error}
        </p>
      )}
    </form>
  );
}
