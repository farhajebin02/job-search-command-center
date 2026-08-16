"use client";

import "@livekit/components-styles";
import "./globals.css";
import { LiveKitRoom, RoomAudioRenderer } from "@livekit/components-react";
import { useEffect, useState } from "react";
import { fetchToken } from "@/lib/api";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const [conn, setConn] = useState<{ token: string; url: string } | null>(null);

  useEffect(() => {
    fetchToken("operator").then(setConn).catch(console.error);
  }, []);

  return (
    <html lang="en" className="dark">
      <body className="bg-neutral-950 text-neutral-100 antialiased">
        {conn ? (
          <LiveKitRoom
            token={conn.token}
            serverUrl={conn.url}
            connect
            // Connect with the mic closed — nothing is captured until the user
            // opens it from the mic control.
            audio={false}
            video={false}
          >
            <RoomAudioRenderer />
            {children}
          </LiveKitRoom>
        ) : (
          <div className="grid min-h-dvh place-items-center text-neutral-500">
            Connecting…
          </div>
        )}
      </body>
    </html>
  );
}
