import requests

from bitso_bot.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def enviar_alerta_telegram(mensaje):
    """Envía una notificación push a Telegram y también imprime en consola."""
    print(mensaje.replace("<b>", "").replace("</b>", "").replace("• ", "   -> "))
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"⚠️ No se pudo enviar la alerta a Telegram: {e}")
