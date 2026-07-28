import sys
import os
import argparse
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("Main")

from config import INPUT_BOOKS_DIR, BOOKS_DIR, TELEGRAM_BOT_TOKEN
from src.importer import EPUBImporter
from src.engine import GameEngine
from src.tts import TTSManager
from src.voice_parser import VoiceParser

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
    token = args.token or TELEGRAM_BOT_TOKEN
    if not token:
        print("❌ Error: Se requiere un token de Telegram. Configúralo en TELEGRAM_BOT_TOKEN o pásalo con --token")
        sys.exit(1)

    from src.bot import TelegramGameBot
    bot = TelegramGameBot(token=token)
    bot.run()

def main():
    parser = argparse.ArgumentParser(description="Motor Narrativo de Librojuegos para Telegram & CLI")
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

    args = parser.parse_args()

    if args.command == "import":
        command_import(args)
    elif args.command == "cli":
        command_cli(args)
    elif args.command == "bot":
        command_bot(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
