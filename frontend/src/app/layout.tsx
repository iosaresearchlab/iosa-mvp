import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/react";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "https://iosaresearch.org";
const TITLE = "IOSA — Institute for Open Social Analytics";
const DESCRIPTION =
  "Independent audit of social media metrics against statistical baselines.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: TITLE,
  description: DESCRIPTION,
  icons: {
    icon: "/favicon.ico",
    apple: "/apple-touch-icon.png",
  },
  openGraph: {
    type: "website",
    siteName: "IOSA",
    title: TITLE,
    description: DESCRIPTION,
    url: SITE_URL,
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: TITLE }],
  },
  twitter: {
    card: "summary_large_image",
    title: TITLE,
    description: DESCRIPTION,
    images: ["/og-image.png"],
  },
  // Codici di verifica di Google Search Console e Bing Webmaster Tools. Si
  // incollano come variabili d'ambiente su Vercel, non nel codice: cambiano se
  // cambia il dominio e non hanno niente da fare nel repository.
  verification: {
    google: process.env.NEXT_PUBLIC_GOOGLE_SITE_VERIFICATION,
    other: process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION
      ? { "msvalidate.01": process.env.NEXT_PUBLIC_BING_SITE_VERIFICATION }
      : undefined,
  },
};

// Dati strutturati: dicono ai motori che cosa e' questo sito, invece di
// lasciarglielo dedurre dal testo. Organization spiega chi siamo, Dataset
// spiega che pubblichiamo misurazioni aperte - ed e' il tipo che vale per un
// progetto di ricerca.
const DATI_STRUTTURATI = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": `${SITE_URL}/#organization`,
      name: "IOSA — Institute for Open Social Analytics",
      alternateName: "IOSA",
      url: SITE_URL,
      logo: `${SITE_URL}/og-image.png`,
      description:
        "Independent, self-funded research project measuring public social media metrics against each channel's own statistical baseline.",
      sameAs: [
        "https://www.instagram.com/iosa.research.lab/",
        "https://x.com/IOSAResearch",
        "https://github.com/iosaresearchlab",
      ],
    },
    {
      "@type": "WebSite",
      "@id": `${SITE_URL}/#website`,
      url: SITE_URL,
      name: TITLE,
      description: DESCRIPTION,
      publisher: { "@id": `${SITE_URL}/#organization` },
    },
    {
      "@type": "Dataset",
      "@id": `${SITE_URL}/#dataset`,
      name: "IOSA Viral Performance Index (VPI)",
      description:
        "Continuously updated measurements of short-form videos against the median views of their own channel's recent videos of the same format, across 34 countries and 13 categories. Free to consult, no signup.",
      url: SITE_URL,
      license: "https://creativecommons.org/licenses/by/4.0/",
      isAccessibleForFree: true,
      creator: { "@id": `${SITE_URL}/#organization` },
      variableMeasured: [
        { "@type": "PropertyValue", name: "VPI ratio", description: "Video views divided by the median views of the same channel's recent videos of the same format." },
        { "@type": "PropertyValue", name: "Baseline score", description: "Median views of the channel's recent videos of the same format." },
        { "@type": "PropertyValue", name: "Engagement score", description: "Public view count at measurement time." },
      ],
    },
  ],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(DATI_STRUTTURATI) }}
        />
        {children}
        <Analytics />
      </body>
    </html>
  );
}