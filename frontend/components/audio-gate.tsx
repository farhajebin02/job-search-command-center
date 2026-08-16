"use client";

import { useRoomContext } from "@livekit/components-react";
import { RoomEvent } from "livekit-client";
import { Volume2 } from "lucide-react";
import { useEffect, useState } from "react";

/**
 * Browsers refuse to play audio until the user has interacted with the page.
 * The room used to connect with `audio` enabled, and that implicit
 * getUserMedia call doubled as the unlock — so nothing ever surfaced this.
 * Now that the mic starts closed, a user who never presses anything hears
 * nothing at all, including the greeting, and the app looks dead.
 */
export function AudioGate() {
  const room = useRoomContext();
  const [blocked, setBlocked] = useState(false);

  useEffect(() => {
    const sync = () => setBlocked(!room.canPlaybackAudio);
    sync();
    room.on(RoomEvent.AudioPlaybackStatusChanged, sync);
    return () => {
      room.off(RoomEvent.AudioPlaybackStatusChanged, sync);
    };
  }, [room]);

  if (!blocked) return null;

  return (
    <button
      type="button"
      onClick={() => void room.startAudio()}
      className="flex items-center justify-center gap-2 rounded-lg border border-amber-600 bg-amber-950 px-3 py-2 text-sm font-medium text-amber-200 hover:bg-amber-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-400"
    >
      <Volume2 className="h-4 w-4" aria-hidden="true" />
      Enable sound
    </button>
  );
}
