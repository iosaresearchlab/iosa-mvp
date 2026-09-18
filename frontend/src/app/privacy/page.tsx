export default function PrivacyPage() {
  return (
    <main className="max-w-4xl mx-auto px-6 py-12 text-slate-800 dark:text-slate-200">
      <h1 className="text-3xl font-bold mb-2">Privacy Policy</h1>
      <p className="text-sm text-slate-500 mb-8">Effective Date: September 19, 2026</p>

      <section className="space-y-6">
        <div>
          <h2 className="text-xl font-semibold mb-2">1. Organization Overview</h2>
          <p>
            IOSA Research Lab ("we", "our", or "us") operates as an independent, self-funded research institute dedicated to quantitative digital media research, algorithmic analytics, and social dynamics modeling through the Viral Performance Index (VPI).
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-2">2. Data Collection & Processing</h2>
          <p>
            Our analytical models process aggregated, publicly available metrics originating from third-party social media platforms for research and statistical evaluation. We do not aggregate or store private personal data from individual platform users. Technical usage logs (such as anonymized IP addresses and browser types) may be temporarily processed to maintain infrastructure security and platform stability.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-2">3. Research Purpose & Data Usage</h2>
          <p>
            All processed data is utilized solely for independent research, baseline calculations, algorithmic modeling, and rendering insights via the VPI platform. We do not sell, license, or transfer user or platform analytics to third-party data brokers for commercial marketing.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-2">4. Third-Party Integrations</h2>
          <p>
            This website and its associated backend engines interact with public API endpoints. Users are encouraged to review the respective terms and privacy policies of the underlying platforms analyzed within our metrics.
          </p>
        </div>

        <div>
          <h2 className="text-xl font-semibold mb-2">5. Official Contact</h2>
          <p>
            For privacy inquiries, data subject requests, or official research correspondence, contact our administration exclusively at:
          </p>
          <p className="font-semibold text-blue-600 dark:text-blue-400 mt-2">
            iosa.research.lab@gmail.com
          </p>
        </div>
      </section>
    </main>
  );
}