'use client';

import { useState } from 'react';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

interface TrophyPayload {
  author: string;
  vpi_ratio: string;
  level_name: string;
  content_title: string;
  date_str: string;
}

export default function BuyTrophyButton({ postData }: { postData: TrophyPayload }) {
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState('');

  const handleBuyTrophy = async () => {
    setLoading(true);
    try {
      // 1. Genera l'immagine e crea il prodotto su Printify
      setStatusText('Generazione targa...');
      const genRes = await fetch('${BACKEND_URL}/api/trophy/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(postData),
      });

      if (!genRes.ok) throw new Error('Errore durante la generazione della targa');
      const genData = await genRes.json();

      // 2. Crea la sessione di checkout Stripe
      setStatusText('Apertura checkout...');
      const checkoutRes = await fetch(
        `${BACKEND_URL}/api/checkout/create-session?printify_product_id=${genData.printify_product_id}&creator_name=${encodeURIComponent(postData.author)}`,
        { method: 'POST' }
      );

      if (!checkoutRes.ok) throw new Error('Errore nella creazione del checkout');
      const checkoutData = await checkoutRes.json();

      // 3. Reindirizza a Stripe
      window.location.href = checkoutData.checkout_url;
    } catch (err: any) {
      alert(err.message || 'Si è verificato un errore');
      setLoading(false);
      setStatusText('');
    }
  };

  return (
    <button
      onClick={handleBuyTrophy}
      disabled={loading}
      className="w-full bg-[#00E5FF] hover:bg-[#00B8D4] text-black font-bold font-mono py-3.5 px-6 rounded-xl transition-all disabled:bg-gray-800 disabled:text-gray-500 cursor-pointer disabled:cursor-not-allowed shadow-lg shadow-[#00E5FF]/10 text-sm"
    >
      {loading ? statusText : 'Ordina Targa Commemorativa (29,00 €)'}
    </button>
  );
}