"use client";

import { useRoomContext, useTrackToggle } from "@livekit/components-react";
import { Track } from "livekit-client";
import { Mic, MicOff } from "lucide-react";
import { useEffect, useRef } from "react";

/** A press shorter than this latches the mic on. Anything longer is read as
 *  hold-to-talk and closes the mic again on release. */
const HOLD_MS = 250;

const isTyping = (target: EventTarget | null) =>
  target instanceof HTMLElement &&
  (target.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));

/**
 * One button serving both gestures the mic needs. The room connects with the
 * mic closed, so nothing is captured until the user asks for it.
 */
export function MicControl({ autoOpen = false }: { autoOpen?: boolean }) {
  const { enabled, toggle, pending } = useTrackToggle({
    source: Track.Source.Microphone,
  });
  const room = useRoomContext();

  // Used by the practice route, where holding a button through a full mock
  // interview would be miserable. Runs once; muting afterwards must stick.
  const autoOpened = useRef(false);
  useEffect(() => {
    if (!autoOpen || autoOpened.current) return;
    autoOpened.current = true;
    if (!enabled) void toggle(true);
  }, [autoOpen, enabled, toggle]);

  const pressedAt = useRef<number | null>(null);
  /** Whether this gesture is what opened the mic. A hold that starts while the
   *  mic is already latched on must not mute it on release. */
  const openedByGesture = useRef(false);
  const spaceHeld = useRef(false);

  // Space is the keyboard equivalent of holding the button. Ignored on
  // key-repeat and while the user is typing in a field.
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat || isTyping(e.target)) return;
      if (enabled) return; // already open — don't fight a latched mic
      e.preventDefault();
      spaceHeld.current = true;
      void toggle(true);
    };
    const up = (e: KeyboardEvent) => {
      if (e.code !== "Space" || !spaceHeld.current) return;
      e.preventDefault();
      spaceHeld.current = false;
      void toggle(false);
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [enabled, toggle]);

  const onPointerDown = (e: React.PointerEvent<HTMLButtonElement>) => {
    // This press is a user gesture, which is the only thing that can lift the
    // browser's audio-playback block. Cheap and idempotent, so just do it on
    // every press rather than tracking whether it's still needed.
    void room.startAudio().catch(() => {});
    // Capture so dragging off the button still delivers pointerup here,
    // otherwise a hold could end with the mic stuck open.
    e.currentTarget.setPointerCapture(e.pointerId);
    pressedAt.current = Date.now();
    openedByGesture.current = !enabled;
    if (!enabled) void toggle(true);
  };

  const onPointerUp = () => {
    const held = Date.now() - (pressedAt.current ?? Date.now());
    pressedAt.current = null;
    if (openedByGesture.current) {
      // Opened by this press: a hold closes on release, a tap stays latched.
      if (held >= HOLD_MS) void toggle(false);
    } else if (held < HOLD_MS) {
      // Tap while already open: mute.
      void toggle(false);
    }
  };

  return (
    <div className="flex flex-col gap-1.5">
      <button
        type="button"
        // Deliberately NOT disabled while pending. The first press carries the
        // getUserMedia permission prompt, so `pending` stays true for as long
        // as the user takes to answer it — disabling the button mid-gesture
        // drops pointer capture and the release event with it, which left the
        // mic in whatever state the press started.
        aria-busy={pending}
        aria-pressed={enabled}
        aria-label={
          enabled
            ? "Microphone on. Click to mute."
            : "Microphone muted. Click to unmute, or hold to talk."
        }
        onPointerDown={onPointerDown}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onContextMenu={(e) => e.preventDefault()}
        className={`flex touch-none select-none items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neutral-400 ${
          pending ? "opacity-70" : ""
        } ${
          enabled
            ? "border-emerald-500 bg-emerald-500/15 text-emerald-300"
            : "border-neutral-700 text-neutral-300 hover:bg-neutral-800"
        }`}
      >
        {enabled ? (
          <Mic className="h-4 w-4" aria-hidden="true" />
        ) : (
          <MicOff className="h-4 w-4" aria-hidden="true" />
        )}
        {enabled ? "Mic on" : "Hold to talk"}
      </button>
      <p className="text-center text-xs text-neutral-600">
        {pending
          ? "Starting microphone…"
          : enabled
            ? "Click to mute"
            : "Click to lock on · hold or Space to talk"}
      </p>
    </div>
  );
}
