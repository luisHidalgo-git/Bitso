import os
import time
import hmac
import hashlib
import requests
from dotenv import load_dotenv

# 1. Cargamos las variables del archivo .env al entorno
load_dotenv()

# 2. Obtenemos las credenciales de forma segura
API_KEY = os.getenv("BITSO_API_KEY")
API_SECRET = os.getenv("BITSO_API_SECRET")

# Validación rápida para asegurarnos de que el archivo .env se leyó bien
if not API_KEY or not API_SECRET:
    print("❌ Error: No se encontraron las credenciales en el archivo .env. Revisa que el archivo exista y tenga las variables correctas.")
    exit(1)

BASE_URL = "https://api.bitso.com"
BOOK = "btc_mxn"  # Mercado con el que operaremos

MONTO_A_INVERTIR = 200.0   # Cantidad en MXN que deseas invertir
SALDO_MINIMO_REQUERIDO = 50.0 # Saldo mínimo en MXN

def crear_firma_bitso(http_method, request_path, payload=""):
    """Genera la firma de seguridad HMAC requerida por Bitso usando las variables cargadas."""
    nonce = str(int(time.time() * 1000))
    message = nonce + http_method + request_path + payload
    signature = hmac.new(
        API_SECRET.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return {
        "Authorization": f"Bitso {API_KEY}:{nonce}:{signature}",
        "Content-Type": "application/json"
    }

def obtener_saldo_mxn():
    path = "/v3/balance/"
    headers = crear_firma_bitso("GET", path)
    
    try:
        response = requests.get(BASE_URL + path, headers=headers)
        data = response.json()
        if data.get('success'):
            balances = data['payload']['balances']
            for b in balances:
                if b['currency'] == 'mxn':
                    return float(b['available'])
    except Exception as e:
        print(f"Error al consultar saldo: {e}")
    return 0.0

def analizar_tendencia_btc():
    url = f"{BASE_URL}/v3/ticker/?book={BOOK}"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get('success'):
            payload = data['payload']
            precio_actual = float(payload['last'])
            variacion_24h = float(payload['change_24'])
            
            # Criterio alcista (ej. variación mayor a 0.8% en 24h)
            es_alcista = variacion_24h > 0.8
            
            return {
                "precio": precio_actual,
                "variacion": variacion_24h,
                "alcista": es_alcista
            }
    except Exception as e:
        print(f"Error al obtener precios: {e}")
    
    return None

def ciclo_principal():
    print("--- Evaluando estado de Bitso y Bitcoin ---")
    
    saldo_disponible = obtener_saldo_mxn()
    print(f"💰 Saldo disponible en MXN: ${saldo_disponible:,.2f}")
    
    if saldo_disponible < SALDO_MINIMO_REQUERIDO:
        print("⚪ No hay suficiente dinero nuevo para trabajar. El bot esperará...")
        return

    tendencia = analizar_tendencia_btc()
    if not tendencia:
        print("No se pudo analizar el mercado en este ciclo.")
        return
    
    print(f"📈 Precio actual BTC: ${tendencia['precio']:,.2f} | Variación 24h: {tendencia['variacion']:+.2f}%")
    
    if tendencia['alcista']:
        print("🚀 ¡Tendencia alcista detectada! El dinero va a trabajar...")
        monto_a_usar = min(MONTO_A_INVERTIR, saldo_disponible)
        print(f"[Simulación] Se habrían invertido ${monto_a_usar} MXN en Bitcoin.")
    else:
        print("🔻 El mercado está bajando o estable. El dinero se queda seguro en efectivo (MXN).")

if __name__ == "__main__":
    print("Iniciando bot inteligente de Bitso con variables protegidas...")
    while True:
        ciclo_principal()
        print("\nEsperando el próximo ciclo de revisión (30 minutos)...\n")
        time.sleep(1800)