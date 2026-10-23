import hashlib
import hmac
import json
import time

import requests

from bitso_bot.config import API_KEY, API_SECRET, BASE_URL, MONEDAS_PERMITIDAS
from bitso_bot.notifications import enviar_alerta_telegram


def crear_firma_bitso(http_method, request_path, payload=""):
    """Genera la firma HMAC-SHA256 requerida por Bitso."""
    nonce = str(int(time.time() * 1000))
    message = nonce + http_method + request_path + payload
    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return {
        "Authorization": f"Bitso {API_KEY}:{nonce}:{signature}",
        "Content-Type": "application/json"
    }


def obtener_balances():
    """Consulta los balances disponibles en la cuenta de Bitso."""
    path = "/v3/balance/"
    headers = crear_firma_bitso("GET", path)
    balances_dict = {"mxn": 0.0}
    try:
        response = requests.get(BASE_URL + path, headers=headers)
        data = response.json()
        if data.get("success"):
            for balance in data["payload"]["balances"]:
                moneda = balance["currency"]
                disponible = float(balance["available"])
                balances_dict[moneda] = disponible
    except Exception as e:
        print(f"Error al consultar balances: {e}")
    return balances_dict


def escanear_mercados():
    """Obtiene y ordena los mercados según su variación de 24h."""
    url = f"{BASE_URL}/v3/ticker/"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get("success"):
            tickers = data["payload"]
            mercados_validos = []

            for ticker in tickers:
                book = ticker["book"]
                if book.endswith("_mxn") and book in MONEDAS_PERMITIDAS:
                    mercados_validos.append({
                        "book": book,
                        "cripto": book.split("_")[0],
                        "precio": float(ticker["last"]),
                        "variacion": float(ticker["change_24"]),
                        "volumen": float(ticker["volume"])
                    })

            mercados_validos.sort(
                key=lambda mercado: mercado["variacion"],
                reverse=True
            )
            return mercados_validos
    except Exception as e:
        print(f"Error al escanear mercados: {e}")

    return []


def ejecutar_orden(book, side, tipo_monto, valor):
    """Envía órdenes de mercado a Bitso."""
    path = "/v3/orders/"
    payload_data = {
        "book": book,
        "side": side,
        "type": "market",
        tipo_monto: str(valor)
    }
    payload_str = json.dumps(payload_data)
    headers = crear_firma_bitso("POST", path, payload_str)

    try:
        response = requests.post(BASE_URL + path, headers=headers, data=payload_str)
        resultado = response.json()
        if resultado.get("success"):
            enviar_alerta_telegram(
                f"✅ <b>Orden aceptada por Bitso</b>\n"
                f"• Acción: {side.upper()}\n• Mercado: {book.upper()}"
            )
            return True
        enviar_alerta_telegram(
            f"⚠️ <b>Bitso rechazó la orden</b>\n"
            f"• Mercado: {book.upper()}\n• Motivo: {resultado.get('error')}"
        )
    except Exception as e:
        enviar_alerta_telegram(
            f"❌ <b>Error crítico al enviar orden</b> en {book.upper()}: {e}"
        )
    return False
