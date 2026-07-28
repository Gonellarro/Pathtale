import os
import json
import logging
from pathlib import Path
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from config import TELEGRAM_BOT_TOKEN, BOOKS_DIR
from src.engine import GameEngine
from src.stt import STTManager
from src.voice_parser import VoiceParser

logger = logging.getLogger("TelegramBot")

class TelegramGameBot:
    def __init__(self, engine: Optional[GameEngine] = None, token: str = TELEGRAM_BOT_TOKEN):
        self.token = token
        self.engine = engine or GameEngine()
        self.stt_manager = STTManager()
        self.voice_parser = VoiceParser()
        self.temp_dir = Path("data/temp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        books = self.engine.list_books()
        if not books:
            await update.message.reply_text(
                "¡Hola! Bienvenido al motor de Librojuegos.\n\n"
                "Actualmente no hay ningún libro cargado. Importa un EPUB primero."
            )
            return

        # Use first book by default or list options
        book = books[0]
        state = self.engine.start_game(user.id, book["book_id"])
        
        await update.message.reply_text(
            f"📖 *{book['title']}*\n\n¡Comenzamos tu aventura!",
            parse_mode="Markdown"
        )
        await self._send_node_state(update.effective_chat.id, state, context)

    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        books = self.engine.list_books()
        if books:
            book = books[0]
            state = self.engine.start_game(user.id, book["book_id"])
            await update.message.reply_text("🔄 Reiniciando partida...")
            await self._send_node_state(update.effective_chat.id, state, context)

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = query.from_user.id

        if data.startswith("choice:"):
            parts = data.split(":")
            choice_id = int(parts[1])
            target_node = parts[2]
            book_id = parts[3]

            state = self.engine.get_current_state(user_id, book_id)
            if state:
                choices = state["current_node"]["choices"]
                chosen = next((c for c in choices if c["choice_id"] == choice_id), None)
                if chosen:
                    chosen["book_id"] = book_id
                    new_state = self.engine.make_choice(user_id, chosen)
                    if new_state:
                        await self._send_node_state(query.message.chat_id, new_state, context)

    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        voice = update.message.voice
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        state = self.engine.get_current_state(user_id)
        if not state:
            await update.message.reply_text("Usa /start para iniciar el juego.")
            return

        choices = state["current_node"]["choices"]
        book_id = state["book_id"]

        # Download voice file
        voice_file = await context.bot.get_file(voice.file_id)
        ogg_path = self.temp_dir / f"voice_{user_id}_{voice.file_id}.ogg"
        await voice_file.download_to_drive(ogg_path)

        # Transcribe with Whisper
        await update.message.reply_text("🎙️ *Escuchando audio...*", parse_mode="Markdown")
        transcription = self.stt_manager.transcribe(ogg_path)

        if ogg_path.exists():
            ogg_path.unlink()

        if not transcription:
            await update.message.reply_text("❌ No se pudo transcribir el audio. Por favor, intenta de nuevo o pulsa un botón.")
            return

        await update.message.reply_text(f"🗣️ Transcripción: *\"{transcription}\"*", parse_mode="Markdown")

        # Parse intent
        chosen_choice = self.voice_parser.parse_intent(transcription, choices)
        if chosen_choice:
            chosen_choice["book_id"] = book_id
            await update.message.reply_text(f"✅ Entendido: *{chosen_choice['text']}*", parse_mode="Markdown")
            new_state = self.engine.make_choice(user_id, chosen_choice)
            if new_state:
                await self._send_node_state(chat_id, new_state, context)
        else:
            await update.message.reply_text(
                "❓ No pude determinar tu elección a partir del audio. Por favor, usa los botones de abajo o especifica el número de opción."
            )

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id

        state = self.engine.get_current_state(user_id)
        if not state:
            await update.message.reply_text("Usa /start para comenzar a jugar.")
            return

        choices = state["current_node"]["choices"]
        book_id = state["book_id"]

        chosen_choice = self.voice_parser.parse_intent(text, choices)
        if chosen_choice:
            chosen_choice["book_id"] = book_id
            new_state = self.engine.make_choice(user_id, chosen_choice)
            if new_state:
                await self._send_node_state(chat_id, new_state, context)
        else:
            await update.message.reply_text("Por favor selecciona una de las opciones disponibles.")

    async def _send_node_state(self, chat_id: int, state: dict, context: ContextTypes.DEFAULT_TYPE):
        node = state["current_node"]
        book_id = state["book_id"]
        book_dir = BOOKS_DIR / book_id

        title = node.get("title", "")
        text = node.get("text", "")
        images = node.get("images", [])
        audio_rel = node.get("audio")
        choices = node.get("choices", [])

        # Send Image if available
        if images:
            img_path = book_dir / images[0]
            if img_path.exists():
                with open(img_path, 'rb') as photo:
                    await context.bot.send_photo(chat_id=chat_id, photo=photo)

        # Format node text
        message_text = f"📍 *{title}*\n\n{text}"
        if len(message_text) > 4000:
            message_text = message_text[:3990] + "...\n(texto truncado)"

        # Prepare Inline Keyboard Buttons
        keyboard = []
        for c in choices:
            btn_text = f"[{c['choice_id']}] {c['text']}"
            if len(btn_text) > 60:
                btn_text = btn_text[:57] + "..."
            callback_data = f"choice:{c['choice_id']}:{c['target_node']}:{book_id}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])

        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

        # Send Pre-rendered Audio if available
        if audio_rel:
            audio_path = book_dir / audio_rel
            if audio_path.exists():
                try:
                    with open(audio_path, 'rb') as audio_file:
                        await context.bot.send_audio(chat_id=chat_id, audio=audio_file, caption=f"🔊 Audio {title}")
                except Exception as e:
                    logger.error(f"Error sending audio message: {e}")

    def run(self):
        if not self.token:
            raise ValueError("TELEGRAM_BOT_TOKEN is not set! Set it in your environment or config.py.")
        app = ApplicationBuilder().token(self.token).build()
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("restart", self.restart_command))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
        
        logger.info("Bot starting polling...")
        app.run_polling()
