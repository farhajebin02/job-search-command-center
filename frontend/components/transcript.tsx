"use client";

import {
  useChat,
  useLocalParticipant,
  useTranscriptions,
} from "@livekit/components-react";
import { useEffect, useRef } from "react";

/** Set on a transcription stream once the segment stops being revised. This is
 *  ParticipantAgentAttributes.TranscriptionFinal, which components-react does
 *  not re-export, so the key is spelled out here. */
const FINAL_ATTR = "lk.transcription_final";

/** How close to the bottom still counts as "following along", in px. */
const PINNED_SLACK = 24;

type Entry = {
  id: string;
  at: number;
  mine: boolean;
  text: string;
  interim: boolean;
  typed: boolean;
};

export function Transcript({
  agentLabel = "Co-pilot",
  /** Sizing is the caller's business: the rail fills leftover height, the
   *  practice screen wants a fixed panel. */
  className = "flex-1",
}: {
  agentLabel?: string;
  className?: string;
}) {
  const segments = useTranscriptions();
  const { chatMessages } = useChat();
  const { localParticipant } = useLocalParticipant();
  const scroller = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);

  // Spoken and typed turns share one timeline. Ordered by when each began, not
  // by arrival — a slow final revision must not jump ahead of what came after.
  const entries: Entry[] = [
    ...segments.map((s) => ({
      id: s.streamInfo.id,
      at: s.streamInfo.timestamp,
      mine: s.participantInfo.identity === localParticipant.identity,
      text: s.text,
      // Only dim what we know is still being revised: if the attribute is
      // absent, treat the text as settled rather than dimming everything.
      interim: String(s.streamInfo.attributes?.[FINAL_ATTR] ?? "true") === "false",
      typed: false,
    })),
    ...chatMessages.map((m) => ({
      id: m.id,
      at: m.timestamp,
      mine: m.from?.identity === localParticipant.identity,
      text: m.message,
      interim: false,
      typed: true,
    })),
  ].sort((a, b) => a.at - b.at);

  // Total characters rendered: grows on every token, including revisions to a
  // segment already on screen, which array identity alone would miss.
  const rendered = entries.reduce((n, e) => n + e.text.length, 0);

  // Follow the conversation, but only while the user is already at the bottom.
  // Scrolling up to re-read something must not get yanked back down on the
  // next token.
  useEffect(() => {
    const el = scroller.current;
    if (el && pinned.current) el.scrollTop = el.scrollHeight;
  }, [rendered]);

  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    pinned.current =
      el.scrollHeight - el.scrollTop - el.clientHeight < PINNED_SLACK;
  };

  return (
    // Deliberately not an aria-live region: partial results rewrite themselves
    // on every token, which would make a screen reader re-announce the whole
    // conversation continuously. The status line above carries announcements.
    <div
      ref={scroller}
      onScroll={onScroll}
      className={`${className} space-y-2.5 overflow-y-auto rounded-lg bg-neutral-900 p-3 text-sm leading-relaxed`}
    >
      {entries.length === 0 ? (
        <p className="text-neutral-500">Transcript appears here.</p>
      ) : (
        entries.map((e) => (
          <p key={e.id}>
            <span
              className={`mr-1.5 text-xs font-medium uppercase tracking-wide ${
                e.mine ? "text-neutral-500" : "text-emerald-500"
              }`}
            >
              {e.mine ? "You" : agentLabel}
              {e.typed && <span className="ml-1 normal-case">(typed)</span>}
            </span>
            <span className={e.interim ? "text-neutral-500" : "text-neutral-300"}>
              {e.text}
            </span>
          </p>
        ))
      )}
    </div>
  );
}
