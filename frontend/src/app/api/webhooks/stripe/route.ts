import { NextResponse } from 'next/server';
import Stripe from 'stripe';
import { createClient } from '@supabase/supabase-js';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', { apiVersion: '2023-10-16' as any });
const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL || '', process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '');

export async function POST(req: Request) {
  const body = await req.text();
  const sig = req.headers.get('stripe-signature') || '';

  let event: Stripe.Event;

  try {
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET || '');
  } catch (err: any) {
    return NextResponse.json({ error: `Webhook Error: ${err.message}` }, { status: 400 });
  }

  if (event.type === 'checkout.session.completed') {
    const session = event.data.object as Stripe.Checkout.Session;
    const { claimToken, productType } = session.metadata || {};
    const shippingDetails = session.shipping_details;

    // 1. Salva/Aggiorna la tabella 'claims' su Supabase
    await supabase.from('claims').insert({
      status: 'paid',
      product_selected: productType,
      stripe_session_id: session.id,
      customer_email: session.customer_email,
      shipping_name: shippingDetails?.name,
      shipping_address: shippingDetails?.address,
    });

    // 2. Invia l'ordine a Printify via API
    if (process.env.PRINTIFY_API_TOKEN && process.env.PRINTIFY_SHOP_ID) {
      await fetch(`https://api.printify.com/v1/shops/${process.env.PRINTIFY_SHOP_ID}/orders.json`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${process.env.PRINTIFY_API_TOKEN}`,
        },
        body: JSON.stringify({
          external_id: session.id,
          line_items: [
            {
              product_id: 'ID_PRODOTTO_PRINTIFY', // ID del prodotto creato su Printify
              variant_id: 12345, // ID variante (es. Tazza Standard)
              quantity: 1,
            },
          ],
          address_to: {
            first_name: shippingDetails?.name?.split(' ')[0] || 'Customer',
            last_name: shippingDetails?.name?.split(' ').slice(1).join(' ') || 'IOSA',
            email: session.customer_email,
            address1: shippingDetails?.address?.line1,
            city: shippingDetails?.address?.city,
            zip: shippingDetails?.address?.postal_code,
            country: shippingDetails?.address?.country,
          },
        }),
      });
    }
  }

  return NextResponse.json({ received: true });
}