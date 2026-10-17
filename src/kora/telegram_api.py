import httpx


def send_message(token: str, chat_id: int, text: str, reply_to: int | None = None) -> None:
    """Resposta síncrona via Bot API; o worker não depende do python-telegram-bot."""
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    if reply_to:
        payload["reply_parameters"] = {"message_id": reply_to, "allow_sending_without_reply": True}
    httpx.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=15).raise_for_status()
