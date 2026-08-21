import os
from generate_trophy import create_trophy_image
from printify_service import upload_image_to_printify, create_dynamic_mug_product

def generate_and_publish_trophy(author, vpi_ratio, level_name, content_title, date_str):
    """
    Pipeline End-to-End:
    1. Genera l'immagine della targa personalizzata
    2. Carica l'immagine su Printify
    3. Crea il prodotto Tazza su Printify
    4. Ritorna l'ID prodotto Printify
    """
    # Nome file temporaneo per l'immagine
    temp_img_path = f"trophy_{author.lower().replace(' ', '_')}.png"

    try:
        print(f"\n1. Generazione targa per {author}...")
        create_trophy_image(
            author=author,
            vpi_ratio=vpi_ratio,
            level_name=level_name,
            content_title=content_title,
            date_str=date_str,
            output_path=temp_img_path
        )

        print("2. Caricamento targa su Printify...")
        image_id = upload_image_to_printify(temp_img_path)

        print("3. Creazione prodotto Tazza su Printify...")
        product_id = create_dynamic_mug_product(image_id, creator_name=author)

        print(f"✅ Pipeline completata con successo! Printify Product ID: {product_id}")
        return product_id

    finally:
        # Pulizia del file PNG locale temporaneo
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)

if __name__ == "__main__":
    # Test della pipeline completa con un comando solo
    generate_and_publish_trophy(
        author="MrBeast",
        vpi_ratio="24.5",
        level_name="Lvl 5 - Outlier",
        content_title="$1 vs $500,000 Plane Ticket!",
        date_str="2026-08-20"
    )