/**
 * L'unico piede del sito (UI-4, 01/10/2026), montato dal layout radice.
 */
import Link from 'next/link';
import { FileText, Info, Mail, ShieldCheck } from 'lucide-react';
import { Logo } from '@/components/Logo';

export function SiteFooter() {
  return (
    <footer data-site-footer className="w-full bg-[#020305] border-t border-gray-800/80 pt-6 pb-5 px-6 md:px-12 mt-8 text-xs font-mono text-gray-400">
      <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-6 pb-5 border-b border-gray-800/60">
        <div className="md:col-span-2 space-y-2">
          <Logo altezza={72} />
          <p className="text-[11px] text-gray-400 font-sans leading-relaxed max-w-md">
            An independent, self-funded research project with no profit purpose, measuring how long-form videos first observed in YouTube&apos;s Most Popular charts perform against each channel&apos;s own baseline.
          </p>
          <p className="text-[10px] text-gray-500 font-sans leading-relaxed max-w-md" data-vpi-definition>
            VPI = E<sub>act</sub> / E<sub>base</sub> — a video&apos;s views divided by the median views of the same channel&apos;s long-form videos published 7-90 days before it. For now only long-form videos (over 3 minutes) are measured. It is our own measurement, not a certification issued by any authority.
          </p>
        </div>
        <div className="space-y-2">
          <span className="text-white font-bold text-xs tracking-wider uppercase block border-b border-gray-800 pb-1">Governance & Legal</span>
          <ul className="space-y-2 text-[11px]">
            <li><a href="/privacy.html" className="hover:text-[#00E5FF] transition-colors flex items-center gap-1.5"><ShieldCheck className="w-3 h-3 text-cyan-400" aria-hidden /> Privacy Policy</a></li>
            <li><a href="/terms.html" className="hover:text-[#00E5FF] transition-colors flex items-center gap-1.5"><FileText className="w-3 h-3 text-cyan-400" aria-hidden /> Terms of Service</a></li>
            <li><Link href="/#methodology" className="hover:text-[#00E5FF] transition-colors flex items-center gap-1.5"><Info className="w-3 h-3 text-cyan-400" aria-hidden /> VPI Methodology Standard</Link></li>
          </ul>
        </div>
        <div className="space-y-2">
          <span className="text-white font-bold text-xs tracking-wider uppercase block border-b border-gray-800 pb-1">Contact</span>
          <p className="text-[10px] text-gray-400 font-sans leading-relaxed">Questions about a VPI record, or a removal request?</p>
          <a href="mailto:iosa.research.lab@gmail.com" className="inline-flex items-center gap-1.5 bg-gray-900 hover:bg-gray-800 text-white border border-gray-700 px-3 py-1.5 rounded-lg text-[10px] font-mono transition-colors">
            <Mail className="w-3 h-3 text-[#00E5FF]" aria-hidden /> iosa.research.lab@gmail.com
          </a>
        </div>
      </div>
      <div className="max-w-6xl mx-auto pt-4 flex flex-col md:flex-row justify-between items-center gap-3 text-[10px] text-gray-400">
        <p className="text-center md:text-left font-sans">© 2026 Institute for Open Social Analytics (IOSA). Independent, self-funded research project.</p>
        <p className="text-center md:text-right font-sans max-w-xl">Not affiliated with, endorsed by, sponsored by, or associated with YouTube, Google LLC, Instagram, X or Meta.</p>
      </div>
    </footer>
  );
}
