import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // FIX-1c (20/10/2026): a page prerendered by the build may retry a failed
  // database read for ~30 s (leggi(), src/lib/supabase-server.ts); the default
  // 60 s per page left too little room for five slow reads.
  staticPageGenerationTimeout: 120,
  // SOC-W1 (24/10/2026): the sitemap is regenerated at run time (ISR) and lists the
  // published Findings stories, read from content/findings.
  outputFileTracingIncludes: {
    '/sitemap.xml': ['./content/findings/**/*'],
    // SOC-W3: /room?c= serves the room page with the channel's link preview.
    '/room/creator': ['./public/room/index.html'],
  },
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
  // SOC-W3 (24/10/2026): /room?c=<channel_id> is the same page with the channel's link
  // preview (src/app/room/creator/route.ts). beforeFiles: on Vercel the static /room
  // answered before an ordinary rewrite could look at the query (measured 24/10).
  async rewrites() {
    return {
      beforeFiles: [{ source: "/room", has: [{ type: "query", key: "c" }], destination: "/room/creator" }],
      afterFiles: [{ source: "/room", destination: "/room/index.html" }],
      fallback: [],
    };
  },
};

export default nextConfig;
