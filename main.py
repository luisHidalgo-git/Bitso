import os
import time
import hmac
import hashlib
import json
import requests
from dotenv import load_dotenv

# Cargar variables del archivo .env
load_dotenv()

API_KEY = os.getenv("BITSO_API_KEY")
API_SECRET = os.getenv("BITSO_API_SECRET")

if not API_KEY or not API_SECRET:
    print("❌ Error: No se encontraron las credenciales en el archivo .env.")
    exit(1)

BASE_URL = "https://api.bitso.com"

# --- PARÁRMATROS DE LA ESTRATEGIA ---
MONTO_OPERACION_MXN = 200.0       # Cantidad en MXN a gastar en compras
SALDO_MINIMO_REQUERIDO = 50.0     # Saldo mínimo en MXN para operar
UMBRAL_MINIMO_GANANCIA = 1.0      # Porcentaje mínimo de subida para comprar (ej. 1%)

# Lista de monedas permitidas en el escaneo (evita memecoins de alto riesgo)
MONEDAS_PERMITIDAS = ['btc_mxn', 'eth_mxn', 'xrp_mxn', 'sol_mxn']

def crear_firma_bitso(http_method, request_path, payload=""):
    """Genera la firma de seguridad HMAC requerida por Bitso."""
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
    """Consulta los balances disponibles en tu cuenta de Bitso (MXN y criptos)."""
    path = "/v3/balance/"
    headers = crear_firma_bitso("GET", path)
    balances_dict = {"mxn": 0.0}
    try:
        response = requests.get(BASE_URL + path, headers=headers)
        data = response.json()
        if data.get('success'):
            for b in data['payload']['balances']:
                moneda = b['currency']
                disponible = float(b['available'])
                balances_dict[moneda] = disponible
    except Exception as e:
        print(f"Error al consultar balances: {e}")
    return balances_dict

def escanear_mejor_mercado():
    """Escanea los mercados permitidos y encuentra el de mayor crecimiento en 24h."""
    url = f"{BASE_URL}/v3/ticker/"
    try:
        response = requests.get(url)
        data = response.json()
        if data.get('success'):
            tickers = data['payload']
            mercados_validos = []
            
            for t in tickers:
                book = t['book']
                if book.endswith('_mxn') and book in MONEDAS_PERMITIDAS:
                    mercados_validos.append({
                        "book": book,
                        "precio": float(t['last']),
                        "variacion": float(t['change_24']),
                        "volumen": float(t['volume'])
                    })
            
            # Ordenar de mayor a menor según la variación de 24h
            mercados_validos.sort(key=lambda x: x['variacion'], reverse=True)
            
            if mercados_validos:
                return mercados_validos[0]
                
    except Exception as e:
        print(f"Error al escanear mercados: {e}")
    
    return None

def ejecutar_orden(book, side, tipo_monto, valor):
    """Envía una orden de mercado (compra o venta) a Bitso."""
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
    print("\n" + "="*45)
    print("--- INICIANDO CICLO DE EVALUACIÓN ---")
    
    balances = obtener_balances()
    mxn_disponible = balances.get('mxn', 0.0)
    print(f"💰 Saldo MXN disponible: ${mxn_disponible:,.2f}")

    # Analizar el mercado actual
    mejor_mercado = escanear_mejor_mercado()
    if not mejor_mercado:
        print("No se pudo obtener información de los mercados en este ciclo.")
        return
    
    book_actual = mejor_mercado['book']
    cripto_simbolo = book_actual.split('_')[0] # Extrae 'btc', 'eth', etc.
    saldo_cripto_actual = balances.get(cripto_simbolo, 0.0)
    
    print(f"🏆 Mercado líder: {book_actual.upper()}")
    print(f"   -> Precio: ${mejor_mercado['precio']:,.2f} | Variación 24h: {mejor_mercado['variacion']:+.2f}%")
    print(f"   -> Tu saldo en {cripto_simbolo.upper()}: {saldo_cripto_actual:,.8f}")

    # CASO 1: TENDENCIA ALCISTA (El mercado sube -> Comprar)
    if mejor_mercado['variacion'] >= UMBRAL_MINIMO_GANANCIA:
        print(f"🚀 ¡Tendencia alcista detectada en {book_actual.upper()}!")
        if mxn_disponible >= SALDO_MINIMO_REQUERIDO:
            monto_a_gastar = min(MONTO_OPERACION_MXN, mxn_disponible)
            print(f"🔄 Comprando ${monto_a_gastar:,.2f} MXN de {book_actual.upper()}...")
            
            # 🟢 DESCOMENTA LA SIGUIENTE LÍNEA CUANDO ESTÉS LISTO PARA OPERAR CON DINERO REAL:
            # ejecutar_orden(book_actual, side="buy", tipo_monto="minor", valor=monto_a_gastar)
            print(f"[Simulación] Se habrían invertido ${monto_a_gastar} MXN en {book_actual.upper()}.")
        else:
            print("⚪ Oportunidad detectada, pero no hay suficiente saldo en MXN para comprar.")

    # CASO 2: TENDENCIA BAJISTA / ESTABLE (El mercado baja -> Vender y proteger en MXN)
    else:
        print("🔻 El mercado está a la baja o sin fuerza alcista.")
        
        # Revisamos si tenemos saldo de la criptomoneda líder para venderla a MXN
        # Usamos un umbral mínimo (ej. 0.0001 BTC o equivalente en otras monedas) para evitar órdenes vacías
        if saldo_cripto_actual > 0.0001:
            print(f"🛡️ Vendiendo {saldo_cripto_actual:,.8f} {cripto_simbolo.upper()} para resguardar el dinero en MXN...")
            
            # 🟢 DESCOMENTA LA SIGUIENTE LÍNEA CUANDO ESTÉS LISTO PARA OPERAR CON DINERO REAL:
            # ejecutar_orden(book_actual, side="sell", tipo_monto="major", valor=saldo_cripto_actual)
            print(f"[Simulación] Se habrían vendido tus {cripto_simbolo.upper()} de regreso a MXN.")
        else:
            print(f"⚪ El mercado baja, pero no hay saldo significativo de {cripto_simbolo.upper()} para vender. El dinero ya está seguro en MXN.")

if __name__ == "__main__":
    print("Iniciando bot dinámico multi-mercado de Bitso (Modo Seguro)...")
    while True:
        ciclo_principal()
        print("\n⏳ Esperando el próximo ciclo de revisión (30 minutos)...\n")
        time.sleep(1800) # Pausa de 30 minutos entre cada ciclo