import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // FIX-1c (20/10/2026): a page prerendered by the build may retry a failed
  // database read for ~30 s (leggi(), src/lib/supabase-server.ts); the default
  // 60 s per page left too little room for five slow reads.
  staticPageGenerationTimeout: 120,
  // Le pagine legali sono diventate file statici in /public, come richiesto da
  // TikTok (pagine standalone, raggiungibili e stampabili). Questi redirect
  // tengono vivi i vecchi indirizzi /privacy e /terms, che possono essere gia'
  // stati inviati o salvati da qualcuno.
  async redirects() {
    return [
      { source: "/privacy", destination: "/privacy.html", permanent: true },
      { source: "/terms", destination: "/terms.html", permanent: true },
    ];
  },
  // ROOM-1 (08/10/2026): the Breakout Room is a static page in /public/room.
  async rewrites() {
    return [{ source: "/room", destination: "/room/index.html" }];
  },
};

export default nextConfig;
