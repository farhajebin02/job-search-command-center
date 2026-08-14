"use client";

import { useDataChannel } from "@livekit/components-react";
import { useRouter } from "next/navigation";
import { decode } from "@/lib/events";

export function EventBridge() {
  const router = useRouter();

  useDataChannel((msg) => {
    const evt = decode(msg.payload);
    if (!evt) return;
    if (evt.type === "navigate") {
      router.push(evt.payload.path);
      return;
    }
    window.dispatchEvent(new Event("jcc:refresh"));
  });

  return null;
}
