import asyncio
import logging

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .busca import buscar, formatar
from .config import get_settings
from .logs import configurar
from .status import texto_status
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


async def on_buscar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = update.effective_message
    consulta = " ".join(context.args).strip()
    if not consulta:
        await msg.reply_text("Uso: /buscar <termos>. Ex.: /buscar motion claude")
        return
    # Lê as notas do vault; fora do loop para não travar o bot.
    resultados = await asyncio.to_thread(buscar, context.application.bot_data["settings"], consulta)
    await msg.reply_text(formatar(resultados, consulta), disable_web_page_preview=True)


async def on_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Varre o vault para contar pendentes; fora do loop para não travar o bot.
    texto = await asyncio.to_thread(texto_status, context.application.bot_data["settings"])
    await update.effective_message.reply_text(texto, disable_web_page_preview=True)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sem isto, uma falha num comando só aparece no log e o usuário vê o bot mudo."""
    log.error("erro ao tratar a mensagem", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("Deu erro aqui. Detalhes no log do bot.")


def main() -> None:
    settings = get_settings()
    configurar(settings.log_level)
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.bot_data["queue"] = Queue(settings.db_path)
    app.bot_data["settings"] = settings
    only_me = filters.Chat(chat_id=settings.telegram_allowed_chat_id)
    app.add_handler(CommandHandler("buscar", on_buscar, filters=only_me))
    app.add_handler(CommandHandler("status", on_status, filters=only_me))
    app.add_handler(MessageHandler(only_me & filters.TEXT & ~filters.COMMAND, on_message))
    app.add_error_handler(on_error)
    log.info("bot iniciado (long polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
