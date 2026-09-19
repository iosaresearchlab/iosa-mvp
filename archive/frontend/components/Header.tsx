'use client';

import Link from 'next/link';
import { ShieldCheck } from 'lucide-react';

export default function Header() {
  return (
    <header className="w-full border-b border-gray-800 bg-[#070A10]/90 backdrop-blur-md sticky top-0 z-50 px-6 py-4">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        {/* Brand Logo & Name */}
        <Link href="/" className="flex items-center gap-3 group">
          <div className="relative w-9 h-9 flex items-center justify-center bg-gray-950 border border-cyan-500/30 rounded-lg group-hover:border-[#00E5FF] transition-colors">
            <div className="absolute inset-0 bg-[#00E5FF]/10 rounded-lg blur-xs group-hover:bg-[#00E5FF]/20 transition-all"></div>
            <svg
              className="w-5 h-5 text-[#00E5FF] relative z-10"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
            </svg>
          </div>

          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-black tracking-wider text-lg text-white">
                IOSA
              </span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-950 text-[#00E5FF] border border-cyan-500/30">
                OFFICIAL
              </span>
            </div>
            <p className="text-[10px] font-mono text-gray-400 tracking-tight">
              INSTITUTE FOR OPEN SOCIAL ANALYTICS
            </p>
          </div>
        </Link>

        {/* Live Status Badge */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="hidden sm:inline">MONITORING</span> LIVE
          </div>
        </div>
      </div>
    </header>
  );
}