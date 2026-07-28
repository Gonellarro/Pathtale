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

from config import INPUT_BOOKS_DIR, BOOKS_DIR, TELEGRAM_BOT_TOKEN
from src.importer import EPUBImporter, sanitize_book_id
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
    """Checks Libros/ folder and imports/refreshes EPUBs, then generates missing audios in a background thread."""
    logger.info("🔍 Checking Libros/ folder for auto-import...")
    epub_files = list(INPUT_BOOKS_DIR.glob("*.epub"))
    if not epub_files:
        logger.info("ℹ️ No EPUB files found in Libros/ folder.")
        return

    for epub_path in epub_files:
        book_id = get_epub_book_id(epub_path)
        logger.info(f"✨ Processing '{epub_path.name}' (book_id='{book_id}')...")
        importer = EPUBImporter(epub_path)
        importer.process(generate_audios=False)

    def generate_missing_audios_task():
        import threading
        logger.info("🎙️ Background audio generation thread started...")
        for epub_path in epub_files:
            try:
                importer = EPUBImporter(epub_path)
                importer.process(generate_audios=True)
            except Exception as e:
                logger.error(f"Error generating audios for {epub_path.name}: {e}")
        logger.info("✅ Background audio generation completed!")

    import threading
    threading.Thread(target=generate_missing_audios_task, daemon=True).start()

def command_import(args):
    print("==================================================")
    print("📚 IMPORTADOR DE LIBROJUEGOS (EPUB -> IR JSON + AUDIOS)")
    print("==================================================")
    
    epub_files = list(INPUT_BOOKS_DIR.glob("*.epub"))
    if not epub_files:
        print(f"❌ No se encontraron archivos .epub en la carpeta: {INPUT_BOOKS_DIR.resolve()}")
        return

    tts_mgr = TTSManager()
    for epub_path in epub_files:
        print(f"\nImportando: {epub_path.name}...")
        importer = EPUBImporter(epub_path, tts_manager=tts_mgr)
        book_json_path = importer.process(generate_audios=args.audios)
        print(f"✅ ¡Éxito! Libro importado en: {book_json_path}")

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

def command_bot(args):
    token = getattr(args, 'token', None) or TELEGRAM_BOT_TOKEN
    if not token:
        print("❌ Error: Se requiere un token de Telegram. Configúralo en TELEGRAM_BOT_TOKEN o pásalo con --token")
        sys.exit(1)

    from src.bot import TelegramGameBot
    bot = TelegramGameBot(token=token)
    bot.run()

def command_api(args):
    auto_import_if_needed()
    import uvicorn
    host = getattr(args, 'host', '0.0.0.0')
    port = getattr(args, 'port', 8000)
    reload = getattr(args, 'reload', False)
    print(f"🚀 Iniciando Servidor API REST + PWA Web en http://{host}:{port}")
    uvicorn.run("src.api:app", host=host, port=port, reload=reload)

def command_all(args):
    """Runs both API server and Telegram Bot concurrently."""
    auto_import_if_needed()
    print("🚀 Iniciando API REST + PWA Web y Bot de Telegram simultáneamente...")
    api_thread = threading.Thread(target=command_api, args=(args,), daemon=True)
    api_thread.start()

    token = getattr(args, 'token', None) or TELEGRAM_BOT_TOKEN
    if token:
        command_bot(args)
    else:
        print("ℹ️ TELEGRAM_BOT_TOKEN no configurado. Modo PWA Web solo activo.")
        api_thread.join()

def main():
    parser = argparse.ArgumentParser(description="Motor Narrativo de Librojuegos para REST API, PWA, Telegram & CLI")
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Import command
    cmd_imp = subparsers.add_parser("import", help="Importar archivos EPUB")
    cmd_imp.add_argument("--no-audios", dest="audios", action="store_false", help="Desactivar pre-generación de audio TTS")
    cmd_imp.set_defaults(audios=True)

    # CLI runner
    subparsers.add_parser("cli", help="Jugar en la consola de comandos")

    # Bot command
    cmd_bot = subparsers.add_parser("bot", help="Iniciar el Bot de Telegram")
    cmd_bot.add_argument("--token", type=str, help="Token del bot de Telegram")

    # API command
    cmd_api = subparsers.add_parser("api", help="Iniciar el Servidor API REST + PWA (FastAPI)")
    cmd_api.add_argument("--host", type=str, default="0.0.0.0", help="Host servidor (default: 0.0.0.0)")
    cmd_api.add_argument("--port", type=int, default=8000, help="Puerto servidor (default: 8000)")
    cmd_api.add_argument("--reload", action="store_true", help="Auto-reload para desarrollo")

    # All command
    cmd_all = subparsers.add_parser("all", help="Iniciar API REST/PWA y Bot de Telegram a la vez")
    cmd_all.add_argument("--host", type=str, default="0.0.0.0")
    cmd_all.add_argument("--port", type=int, default=8000)
    cmd_all.add_argument("--token", type=str)

    args = parser.parse_args()

    if args.command == "import":
        command_import(args)
    elif args.command == "cli":
        command_cli(args)
    elif args.command == "bot":
        command_bot(args)
    elif args.command == "api":
        command_api(args)
    elif args.command == "all":
        command_all(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
