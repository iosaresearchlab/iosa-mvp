'use client';

import { useState } from 'react';
import { Zap, Loader2, AlertCircle } from 'lucide-react';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface ClaimFormProps {
  claimToken: string;
  authorHandle?: string;
  postData?: { author?: string };
}

interface ValidationError {
  msg?: string;
}

export default function ClaimForm({ claimToken, authorHandle, postData }: ClaimFormProps) {
  // Resolve creator handle safely whether passed directly or via postData
  const activeAuthor = authorHandle || postData?.author || 'Creator';

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [productType, setProductType] = useState('Official Commemorative Mug ($19.00)');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

  // Syntax validation for email
  const isValidEmail = (emailStr: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailStr);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg('');

    // Pre-flight frontend checks
    if (!name.trim()) {
      setErrorMsg('Please enter the recipient full name.');
      return;
    }

    if (!email.trim() || !isValidEmail(email)) {
      setErrorMsg('Please enter a valid email address (e.g. name@domain.com).');
      return;
    }

    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/api/checkout/create-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          claimToken,
          authorHandle: activeAuthor,
          email,
          name,
          productType,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        let detailMsg = 'Failed to create Stripe checkout session.';
        
        // Safely parse Pydantic/FastAPI validation detail arrays or strings
        if (typeof data.detail === 'string') {
          detailMsg = data.detail;
        } else if (Array.isArray(data.detail)) {
          detailMsg = data.detail.map((err: ValidationError) => err.msg || 'Validation error').join(', ');
        }
        
        throw new Error(detailMsg);
      }

      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      } else {
        setErrorMsg('Invalid response received from payment server.');
        setLoading(false);
      }
    } catch (err: unknown) {
      console.error('Checkout creation error:', err);
      const errorMessage = err instanceof Error ? err.message : 'An error occurred while connecting to the payment service.';
      setErrorMsg(errorMessage);
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {errorMsg && (
        <div className="p-3 bg-red-950/80 border border-red-500/50 text-red-300 text-xs rounded-lg flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      <div>
        <label className="block text-xs font-mono text-gray-400 mb-1">RECIPIENT FULL NAME</label>
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Rick Astley"
          className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-[#00E5FF]"
          required
        />
      </div>

      <div>
        <label className="block text-xs font-mono text-gray-400 mb-1">DELIVERY EMAIL</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="creator@channel.com"
          className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-[#00E5FF]"
          required
        />
      </div>

      <div>
        <label className="block text-xs font-mono text-gray-400 mb-1">TROPHY TYPE</label>
        <select
          value={productType}
          onChange={(e) => setProductType(e.target.value)}
          className="w-full bg-gray-950 border border-gray-800 rounded-lg p-3 text-sm text-[#00E5FF] focus:outline-none focus:border-[#00E5FF]"
        >
          <option value="Official Commemorative Mug ($19.00)">
            Official Commemorative Mug ($19.00 + shipping calculated at checkout)
          </option>
        </select>
      </div>

      <button
        type="submit"
        disabled={loading}
        className="w-full bg-[#00E5FF] hover:bg-cyan-400 text-black font-bold py-3.5 rounded-lg text-sm transition-colors flex items-center justify-center gap-2 mt-4 disabled:opacity-50 cursor-pointer"
      >
        {loading ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <>
            <Zap className="w-4 h-4 fill-black" /> Proceed to Secure Checkout
          </>
        )}
      </button>
    </form>
  );
}