import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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
};

export default nextConfig;
