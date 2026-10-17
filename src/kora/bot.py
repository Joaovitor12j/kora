import asyncio
import logging

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from .config import get_settings
from .correcao import corrigir_categoria, pedido_de_categoria
from .db import CONCLUIDO, FALHOU, Queue
from .urls import canonicalize, extract_urls, needs_resolution, platform_of, resolve_redirects

log = logging.getLogger("kora.bot")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    pedido = pedido_de_categoria(msg.text)
    if pedido and msg.reply_to_message:
        resposta = corrigir_categoria(
            context.application.bot_data["queue"], context.application.bot_data["settings"],
            msg.chat_id, msg.reply_to_message.message_id, pedido)
        await msg.reply_text(resposta)
        return
    urls = extract_urls(msg.text or "")
    if not urls:
        await msg.reply_text("Mande um link para eu salvar.")
        return
    queue: Queue = context.application.bot_data["queue"]
    replies = []
    for url in urls:
        if needs_resolution(url):
            url = await asyncio.to_thread(resolve_redirects, url)
        canonica = canonicalize(url)
        item, created = queue.enqueue(
            url, canonica, platform_of(url), chat_id=msg.chat_id, message_id=msg.message_id
        )
        if created:
            replies.append(f"na fila: {canonica}")
        elif item.status == CONCLUIDO:
            replies.append(f"já salvo: {item.titulo}")
        elif item.status == FALHOU:
            queue.retry(item.id)
            replies.append(f"tentando de novo: {canonica}")
        else:
            replies.append(f"já está na fila: {canonica}")
    await msg.reply_text("\n".join(replies), disable_web_page_preview=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    settings = get_settings()
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["queue"] = Queue(settings.db_path)
    app.bot_data["settings"] = settings
    only_me = filters.Chat(chat_id=settings.telegram_allowed_chat_id)
    app.add_handler(MessageHandler(only_me & filters.TEXT & ~filters.COMMAND, on_message))
    log.info("bot iniciado (long polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
