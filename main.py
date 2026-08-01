import sys
import os
import argparse
import logging
import threading
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("Main")

from config import INPUT_BOOKS_DIR, BOOKS_DIR
from src.importer import EPUBImporter, sanitize_book_id
from src.pdf_importer import PDFImporter
from src.engine import GameEngine
from src.tts import TTSManager
from src.voice_parser import VoiceParser

def get_epub_book_id(epub_path: Path) -> str:
    try:
        with zipfile.ZipFile(epub_path, 'r') as z:
            opf_file = next((name for name in z.namelist() if name.endswith('.opf')), None)
            if opf_file:
                soup_opf = BeautifulSoup(z.read(opf_file).decode('utf-8', errors='ignore'), 'html.parser')
                t_elem = soup_opf.find(['dc:title', 'title'])
                if t_elem and t_elem.text.strip():
                    return sanitize_book_id(t_elem.text.strip())
    except Exception:
        pass
    return sanitize_book_id(epub_path.stem)

def auto_import_if_needed():
    """Checks Libros/ folder and imports/refreshes EPUBs and PDFs structure without forced audio generation on boot."""
    logger.info("🔍 Checking Libros/ folder for auto-import...")
    epub_files = list(INPUT_BOOKS_DIR.glob("*.epub"))
    pdf_files = list(INPUT_BOOKS_DIR.glob("*.pdf"))
    if not epub_files and not pdf_files:
        logger.info("ℹ️ No EPUB or PDF files found in Libros/ folder.")
        return

    for epub_path in epub_files:
        book_id = get_epub_book_id(epub_path)
        logger.info(f"✨ Processing EPUB '{epub_path.name}' (book_id='{book_id}')...")
        importer = EPUBImporter(epub_path)
        importer.process(generate_audios=False)

    for pdf_path in pdf_files:
        logger.info(f"✨ Processing PDF '{pdf_path.name}'...")
        pdf_imp = PDFImporter(pdf_path)
        pdf_imp.process(generate_audios=False)
    logger.info("✅ Libros/ folder metadata import complete.")

def command_import(args):
    print("==================================================")
    print("📚 IMPORTADOR DE LIBROJUEGOS (EPUB / PDF -> IR JSON + AUDIOS)")
    print("==================================================")
    
    epub_files = list(INPUT_BOOKS_DIR.glob("*.epub"))
    pdf_files = list(INPUT_BOOKS_DIR.glob("*.pdf"))
    if not epub_files and not pdf_files:
        print(f"❌ No se encontraron archivos .epub o .pdf en la carpeta: {INPUT_BOOKS_DIR.resolve()}")
        return

    tts_mgr = TTSManager()
    for epub_path in epub_files:
        print(f"\nImportando EPUB: {epub_path.name}...")
        importer = EPUBImporter(epub_path, tts_manager=tts_mgr)
        book_json_path = importer.process(generate_audios=args.audios)
        print(f"✅ ¡Éxito! Libro EPUB importado en: {book_json_path}")

    for pdf_path in pdf_files:
        print(f"\nImportando PDF: {pdf_path.name}...")
        pdf_imp = PDFImporter(pdf_path, tts_manager=tts_mgr)
        book_json_path = pdf_imp.process(generate_audios=args.audios)
        print(f"✅ ¡Éxito! Libro PDF importado en: {book_json_path}")

def command_cli(args):
    engine = GameEngine()
    books = engine.list_books()
    if not books:
        print("❌ No hay libros disponibles. Ejecuta 'python3 main.py import' primero.")
        return

    print("\n--- LIBROS DISPONIBLES ---")
    for idx, b in enumerate(books, 1):
        print(f"{idx}. {b['title']} (ID: {b['book_id']})")

    book_id = books[0]["book_id"]
    user_id = 9999
    state = engine.start_game(user_id, book_id)
    parser = VoiceParser()

    print("\n🎮 ¡Comenzando juego en consola!")
    while state:
        node = state["current_node"]
        print("\n" + "="*50)
        print(f"📍 [{node.get('id')}] {node.get('title')}")
        print("="*50)
        print(node.get("text"))

        choices = node.get("choices", [])
        if not choices:
            print("\n🏁 FIN DE LA AVENTURA.")
            break

        print("\n👇 OPCIONES DISPONIBLES:")
        for c in choices:
            print(f" [{c['choice_id']}] {c['text']} (Página {c['target_display_number']})")

        ans = input("\n> Tu elección (texto o número): ")
        if ans.strip().lower() in ("exit", "quit", "salir"):
            break

        chosen = parser.parse_intent(ans, choices)
        if chosen:
            chosen["book_id"] = book_id
            print(f"-> Elegiste: {chosen['text']}")
            state = engine.make_choice(user_id, chosen)
        else:
            print("❌ No entendí esa opción. Por favor prueba otra vez.")

def command_api(args):
    auto_import_if_needed()
    import uvicorn
    host = getattr(args, 'host', '0.0.0.0')
    port = getattr(args, 'port', 8000)
    reload = getattr(args, 'reload', False)
    print(f"🚀 Iniciando Servidor API REST + PWA Web en http://{host}:{port}")
    uvicorn.run("src/api.py:app" if False else "src.api:app", host=host, port=port, reload=reload)

def main():
    parser = argparse.ArgumentParser(description="Motor Narrativo de Librojuegos para REST API, PWA & CLI")
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Import command
    cmd_imp = subparsers.add_parser("import", help="Importar archivos EPUB")
    cmd_imp.add_argument("--no-audios", dest="audios", action="store_false", help="Desactivar pre-generación de audio TTS")
    cmd_imp.set_defaults(audios=True)

    # CLI runner
    subparsers.add_parser("cli", help="Jugar en la consola de comandos")

    # API command
    cmd_api = subparsers.add_parser("api", help="Iniciar el Servidor API REST + PWA (FastAPI)")
    cmd_api.add_argument("--host", type=str, default="0.0.0.0", help="Host servidor (default: 0.0.0.0)")
    cmd_api.add_argument("--port", type=int, default=8000, help="Puerto servidor (default: 8000)")
    cmd_api.add_argument("--reload", action="store_true", help="Auto-reload para desarrollo")

    # Default all to api if no subcommand
    subparsers.add_parser("all", help="Iniciar Servidor API REST + PWA")

    args = parser.parse_args()

    if args.command == "import":
        command_import(args)
    elif args.command == "cli":
        command_cli(args)
    elif args.command == "api" or args.command == "all":
        command_api(args)
    else:
        command_api(args)

if __name__ == "__main__":
    main()
