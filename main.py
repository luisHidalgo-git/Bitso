import os
import time
import hmac
import hashlib
import json
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BITSO_API_KEY")
API_SECRET = os.getenv("BITSO_API_SECRET")

if not API_KEY or not API_SECRET:
    print("❌ Error: No se encontraron las credenciales en el archivo .env.")
    exit(1)

BASE_URL = "https://api.bitso.com"

# Parámetros de la estrategia
MONTO_OPERACION_MXN = 200.0  
SALDO_MINIMO_REQUERIDO = 50.0
UMBRAL_MINIMO_GANANCIA = 1.0 # Porcentaje mínimo de subida para considerar la compra (ej. 1%)

# Lista blanca opcional de monedas confiables que permites tradear (evita memecoins riesgosas)
MONEDAS_PERMITIDAS = ['btc_mxn', 'eth_mxn', 'xrp_mxn', 'sol_mxn']

def crear_firma_bitso(http_method, request_path, payload=""):
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

def obtener_balances():
    path = "/v3/balance/"
    headers = crear_firma_bitso("GET", path)
    balances_dict = {"mxn": 0.0}
    try:
        response = requests.get(BASE_URL + path, headers=headers)
        data = response.json()
        if data.get('success'):
            for b in data['payload']['balances']:
                if b['currency'] == 'mxn':
                    balances_dict['mxn'] = float(b['available'])
                else:
                    # Guardamos el balance de cualquier otra cripto por si la tiene acumulada
                    balances_dict[b['currency']] = float(b['available'])
    except Exception as e:
        print(f"Error al consultar balances: {e}")
    return balances_dict

def escanear_mejor_mercado():
    """Consulta todos los mercados de Bitso y busca el que tenga mayor crecimiento en MXN."""
    url = f"{BASE_URL}/v3/ticker/"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get('success'):
            tickers = data['payload']
            mercados_validos = []
            
            for t in tickers:
                book = t['book']
                # Filtramos solo los pares contra MXN y que estén en nuestra lista permitida
                if book.endswith('_mxn') and book in MONEDAS_PERMITIDAS:
                    change_24 = float(t['change_24'])
                    price = float(t['last'])
                    volume = float(t['volume'])
                    
                    mercados_validos.append({
                        "book": book,
                        "precio": price,
                        "variacion": change_24,
                        "volumen": volume
                    })
            
            # Ordenamos los mercados de mayor a menor según su variación de 24h
            mercados_validos.sort(key=lambda x: x['variacion'], reverse=True)
            
            if mercados_validos:
                # Devolvemos el mercado con el porcentaje más alto
                return mercados_validos[0]
                
    except Exception as e:
        print(f"Error al escanear mercados: {e}")
    
    return None

def ejecutar_orden(book, side, tipo_monto, valor):
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
        if resultado.get('success'):
            print(f"✅ Orden de {side.upper()} en {book.upper()} ejecutada exitosamente.")
            return True
        else:
            print(f"⚠️ Bitso rechazó la orden: {resultado.get('error')}")
    except Exception as e:
        print(f"Error crítico al enviar la orden: {e}")
    return False

def ciclo_principal():
    print("\n--- Escaneando el mercado global de Bitso ---")
    balances = obtener_balances()
    mxn_disponible = balances.get('mxn', 0.0)
    print(f"💰 Saldo MXN disponible: ${mxn_disponible:,.2f}")

    # Buscamos cuál es la cripto con mejor desempeño en este momento
    mejor_mercado = escanear_mejor_mercado()
    
    if not mejor_mercado:
        print("No se pudo obtener información de los mercados.")
        return
    
    print(f"🏆 Mercado líder actual: {mejor_mercado['book'].upper()}")
    print(f"   -> Precio: ${mejor_mercado['precio']:,.2f} | Variación 24h: {mejor_mercado['variacion']:+.2f}%")

    # DECISIÓN: Si el activo líder supera nuestro umbral de ganancia y tenemos pesos, compramos
    if mejor_mercado['variacion'] >= UMBRAL_MINIMO_GANANCIA:
        if mxn_disponible >= SALDO_MINIMO_REQUERIDO:
            monto_a_gastar = min(MONTO_OPERACION_MXN, mxn_disponible)
            print(f"🚀 ¡Tendencia alcista fuerte en {mejor_mercado['book'].upper()}! Comprando con ${monto_a_gastar} MXN...")
            
            # --- LÍNEA REAL DE COMPRA (Descomenta cuando estés listo) ---
            # ejecutar_orden(mejor_mercado['book'], side="buy", tipo_monto="minor", valor=monto_a_gastar)
            print(f"[Simulación] Se habrían comprado ${monto_a_gastar} MXN de {mejor_mercado['book'].upper()}.")
        else:
            print("⚪ Se detectó oportunidad, pero no hay suficiente saldo en MXN.")
    else:
        print("💤 Ningún mercado cumple con el umbral mínimo de crecimiento. El dinero se queda en MXN.")

if __name__ == "__main__":
    print("Iniciando escáner dinámico multi-mercado de Bitso...")
    while True:
        ciclo_principal()
        print("\nEsperando el próximo ciclo de escaneo (30 minutos)...\n")
        time.sleep(1800)