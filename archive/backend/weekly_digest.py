import os
from dotenv import load_dotenv
from supabase import create_client, Client

from log_iosa import configura, prendi

log = prendi(__name__)

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    log.error("❌ ERRORE: SUPABASE_URL o SUPABASE_KEY non trovate nel file .env")
    exit(1)

def generate_weekly_digest():
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        
        # Selezioniamo solo i campi reali presenti nella tabella 'posts'
        response = (
            supabase.table("posts")
            .select("author_name, vpi_ratio")
            .eq("status", "ACTIVE")
            .order("vpi_ratio", desc=True)
            .limit(3)
            .execute()
        )
        
        posts = response.data
        
        if not posts or len(posts) < 3:
            log.warning("⚠️ Meno di 3 record attivi trovati nel database.")
            return

        top1, top2, top3 = posts[0], posts[1], posts[2]

        def clean_name(name: str) -> str:
            if not name:
                return "Unknown Creator"
            # Rimuove prefissi tecnici come '@a' o '@' se presenti nel nome
            clean = name.lstrip('@a').lstrip('@').strip()
            return clean if clean else name

        log.info("\n==================================================")
        log.info("   SCRIPT REALE YOUTUBE SHORT (ESTRATTO DA DB)")
        log.info("==================================================\n")
        
        log.info("⏱️ [0:00 - 0:08] HOOK")
        log.info('Voiceover: "These 3 YouTube channels completely broke the algorithm this week, and our data proves it. Welcome to the Weekly VPI Outlier Report."\n')
        
        log.info("⏱️ [0:08 - 0:22] TOP 3 & TOP 2")
        log.info(f'Voiceover: "At number 3, {clean_name(top3["author_name"])} pulled a massive {round(top3["vpi_ratio"], 1)}x view multiplier over their baseline. At number 2, {clean_name(top2["author_name"])} generated a {round(top2["vpi_ratio"], 1)}x VPI spike."\n')
        
        log.info("⏱️ [0:22 - 0:42] TOP 1 HYPER OUTLIER")
        log.info(f'Voiceover: "But the absolute biggest anomaly goes to {clean_name(top1["author_name"])}, logging a mind-blowing {round(top1["vpi_ratio"], 1)}x VPI score. That means this single upload performed over {int(top1["vpi_ratio"])} times better than their usual average!"\n')
        
        log.info("⏱️ [0:42 - 0:55] CALL TO ACTION")
        log.info('Voiceover: "Want us to analyze your channel\'s metrics? Drop your YouTube handle in the comments below, and subscribe for next week\'s report."\n')

    except Exception as e:
        log.error(f"❌ Errore durante il recupero dei dati: {e}")

if __name__ == "__main__":
    configura()
    generate_weekly_digest()