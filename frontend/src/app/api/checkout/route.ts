import { NextResponse } from 'next/server';
import Stripe from 'stripe';

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || '', {
  apiVersion: '2023-10-16' as any,
});

export async function POST(request: Request) {
  try {
    const { claimToken, authorHandle, email, name, productType } = await request.json();
    const baseUrl = process.env.NEXT_PUBLIC_BASE_URL || 'http://localhost:3000';

    const priceAmount = productType.includes('Mug') ? 1900 : 2900; // espresso in centesimi (€19.00 o €29.00)

    const session = await stripe.checkout.sessions.create({
      payment_method_types: ['card'],
      shipping_address_collection: {
        allowed_countries: ['IT', 'US', 'DE', 'FR', 'ES', 'GB'], 
      },
      line_items: [
        {
          price_data: {
            currency: 'eur',
            product_data: {
              name: `IOSA Official Trophy — ${productType}`,
              description: `Accredited Viral Outlier Award for creator @${authorHandle}`,
            },
            unit_amount: priceAmount,
          },
          quantity: 1,
        },
      ],
      mode: 'payment',
      customer_email: email,
      success_url: `${baseUrl}/claim/${claimToken}?success=true`,
      cancel_url: `${baseUrl}/claim/${claimToken}?canceled=true`,
      metadata: {
        claimToken,
        recipientName: name,
        productType,
      },
    });

    return NextResponse.json({ url: session.url });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}