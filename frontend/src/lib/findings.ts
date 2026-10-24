/**
 * SOC-W1 (24/10/2026): the Findings stories, read from the repository at build time.
 *
 * One story = three files, committed together:
 *   frontend/content/findings/<slug>.md         front matter + Markdown body
 *   frontend/content/findings/<slug>.data.json  the figures the chart draws
 *   tools/findings/<slug>.sql                   the read-only query that produced them
 *
 * Front matter (one `key: value` per line between two `---` lines):
 *   title, date (YYYY-MM-DD), summary, status (draft | published),
 *   chart (the data file name), source_sql (the SQL file name), og_title.
 *
 * Only published stories are built, linked and listed in the sitemap: a draft
 * has no route (dynamicParams = false on the pages). A published story with a
 * missing field or file fails the build instead of going out broken.
 * The URL is /insights/findings/<slug>: the slug is the file name and never
 * changes once published.
 */
import fs from 'node:fs';
import path from 'node:path';

export const FINDINGS_DIR = path.join(process.cwd(), 'content/findings');
export const FINDINGS_SQL_DIR = path.join(process.cwd(), '..', 'tools/findings');

const CAMPI = ['title', 'date', 'summary', 'status', 'chart', 'source_sql', 'og_title'] as const;
type Campo = (typeof CAMPI)[number];

export type FindingMeta = Record<Campo, string> & { slug: string; status: 'draft' | 'published' };

export type ChartPoint = { label: string; value: number };
export type ChartData = {
  /** bar: one horizontal bar per point; line: points in order (e.g. days). */
  type: 'bar' | 'line';
  /** The figure the chart shows, in words ("Records first observed per day"). */
  measure: string;
  /** Suffix for values ("×", " views"); empty for counts. */
  unit?: string;
  /** The day of the reading the figures come from, YYYY-MM-DD. */
  reading_date: string;
  points: ChartPoint[];
  /** One line under the chart (population, exclusions). */
  note?: string;
};

export type Finding = { meta: FindingMeta; body: string; data: ChartData };

const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const GIORNO = /^\d{4}-\d{2}-\d{2}$/;

export function parseFrontMatter(testo: string): { campi: Record<string, string>; body: string } {
  const m = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(testo);
  if (!m) throw new Error('front matter missing (--- lines)');
  const campi: Record<string, string> = {};
  for (const riga of m[1].split(/\r?\n/)) {
    if (!riga.trim() || riga.trim().startsWith('#')) continue;
    const i = riga.indexOf(':');
    if (i < 1) throw new Error(`front matter line without "key:": ${riga}`);
    let v = riga.slice(i + 1).trim();
    if (/^".*"$/.test(v) || /^'.*'$/.test(v)) v = v.slice(1, -1);
    campi[riga.slice(0, i).trim()] = v;
  }
  return { campi, body: m[2] };
}

function leggiMeta(slug: string): { meta: FindingMeta; body: string } {
  const { campi, body } = parseFrontMatter(fs.readFileSync(path.join(FINDINGS_DIR, `${slug}.md`), 'utf8'));
  const status = campi.status;
  if (status !== 'draft' && status !== 'published') throw new Error(`${slug}: status must be draft or published`);
  if (status === 'published') {
    for (const c of CAMPI) if (!campi[c]) throw new Error(`${slug}: front matter "${c}" missing`);
    if (!GIORNO.test(campi.date)) throw new Error(`${slug}: date must be YYYY-MM-DD`);
  }
  const meta = { ...Object.fromEntries(CAMPI.map((c) => [c, campi[c] ?? ''])), slug, status } as FindingMeta;
  return { meta, body };
}

export function leggiDati(meta: FindingMeta): ChartData {
  const d = JSON.parse(fs.readFileSync(path.join(FINDINGS_DIR, meta.chart), 'utf8')) as ChartData;
  if (d.type !== 'bar' && d.type !== 'line') throw new Error(`${meta.slug}: chart type must be bar or line`);
  if (!d.measure || !GIORNO.test(d.reading_date || '')) throw new Error(`${meta.slug}: chart needs measure and reading_date`);
  if (!Array.isArray(d.points) || !d.points.length || d.points.some((p) => typeof p.value !== 'number' || !p.label)) {
    throw new Error(`${meta.slug}: chart points must be {label, value} with a number`);
  }
  return d;
}

/** Every story on disk, drafts included, newest first. */
export function tutteLeStorie(): FindingMeta[] {
  if (!fs.existsSync(FINDINGS_DIR)) return [];
  return fs
    .readdirSync(FINDINGS_DIR)
    .filter((f) => f.endsWith('.md'))
    .map((f) => f.slice(0, -3))
    .filter((slug) => {
      if (!SLUG.test(slug)) throw new Error(`findings: "${slug}.md" is not a valid slug (a-z, 0-9, dashes)`);
      return true;
    })
    .map((slug) => leggiMeta(slug).meta)
    .sort((a, b) => (b.date || '').localeCompare(a.date || '') || a.slug.localeCompare(b.slug));
}

/** The published stories, newest first (front matter only: the sitemap reads this at run time too). */
export function storiePubblicate(): FindingMeta[] {
  return tutteLeStorie().filter((m) => m.status === 'published');
}

/** A published story, or null (a draft or a missing slug has no page). */
export function storia(slug: string): Finding | null {
  if (!SLUG.test(slug) || !fs.existsSync(path.join(FINDINGS_DIR, `${slug}.md`))) return null;
  const { meta, body } = leggiMeta(slug);
  if (meta.status !== 'published') return null;
  // Read at build time only (the pages are static): the query behind the figures must be committed.
  // tools/ sits outside the frontend; where a build cannot see it, tests/test_findings.py
  // (CI, every push) holds the same rule.
  if (fs.existsSync(FINDINGS_SQL_DIR) && !fs.existsSync(path.join(FINDINGS_SQL_DIR, meta.source_sql))) {
    throw new Error(`${slug}: tools/findings/${meta.source_sql} missing (the query behind the figures is committed with them)`);
  }
  return { meta, body, data: leggiDati(meta) };
}

/** "24 October 2026". */
export function dataLunga(iso: string): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
}

/** The figure the chart and the OG image lead with: the largest value. */
export function figuraPrincipale(d: ChartData): ChartPoint {
  return d.points.reduce((a, b) => (b.value > a.value ? b : a));
}

export function formatValore(v: number, unit = ''): string {
  const n = Number.isInteger(v) ? v.toLocaleString('en-US') : v.toLocaleString('en-US', { maximumFractionDigits: 1 });
  return `${n}${unit}`;
}
