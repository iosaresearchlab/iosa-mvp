import Link from 'next/link';

export default function TrophySuccessPage() {
  return (
    <div style={{ backgroundColor: '#0A0C10', color: '#fff', minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif' }}>
      <div style={{ border: '1px solid #00E5FF', padding: '40px', borderRadius: '8px', textAlign: 'center', maxWidth: '500px' }}>
        <h1 style={{ color: '#00E5FF', marginBottom: '10px' }}>Accreditamento Confermato</h1>
        <p style={{ color: '#9CA3AF', marginBottom: '20px' }}>
          Il pagamento è stato completato con successo. La tua targa commemorativa è stata inviata in produzione e riceverai i dettagli di tracciamento via e-mail.
        </p>
        <Link href="/" style={{ color: '#00E5FF', textDecoration: 'underline' }}>
          Torna alla Dashboard
        </Link>
      </div>
    </div>
  );
}