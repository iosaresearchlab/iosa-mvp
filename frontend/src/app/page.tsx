import type { Metadata } from 'next';
import HomePage from '@/components/HomePage';

// SEO-1 (07/10/2026): the home writes its filters and its page into the URL
// (HomeArchive, router.push), so every filtered or paginated home is the same
// page under another address. They all name / as canonical (metadataBase is
// set in layout.tsx). The page itself is a client component and cannot export
// metadata: it lives in components/HomePage.tsx.
export const metadata: Metadata = {
  alternates: { canonical: '/' },
};

export default function Page() {
  return <HomePage />;
}
