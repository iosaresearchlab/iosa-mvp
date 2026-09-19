export default function TermsPage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-12 text-slate-800 dark:text-slate-200">
      <h1 className="text-3xl font-bold mb-2">Terms of Service</h1>
      <p className="text-sm text-slate-500 mb-8">Effective Date: September 19, 2026</p>

      <section className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold mb-2">1. Acceptance of Terms</h2>
          <p>
            By accessing or interacting with the platform operated by IOSA Research Lab, you agree to abide by these Terms of Service. The service is provided by an independent, self-funded research institute for analytical and informational purposes.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-2">2. Research Disclaimer & Limit of Liability</h2>
          <p>
            The Viral Performance Index (VPI), baseline ratios, and associated data visualizations are experimental research outputs. Information is provided on an "as is" and "as available" basis without express or implied warranties. IOSA Research Lab assumes no liability for decisions or actions taken based upon metrics published on this platform.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-2">3. Intellectual Property Rights</h2>
          <p>
            All proprietary analytical methodologies, VPI score calculations, user interface components, and compiled research frameworks are the intellectual property of IOSA Research Lab.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-2">4. Acceptable Platform Use</h2>
          <p>
            You agree not to disrupt platform operations, perform unauthorized automated scraping against non-public endpoints, or attempt to reverse-engineer proprietary algorithms without explicit authorization from our research team.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-2">5. Official Inquiries</h2>
          <p>
            All formal notices, legal communications, or institutional inquiries must be directed to:
          </p>
          <p className="font-semibold text-blue-600 dark:text-blue-400 mt-2">
            iosa.research.lab@gmail.com
          </p>
        </div>
      </section>
    </main>
  );
}