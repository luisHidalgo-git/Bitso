import os
import time
import hmac
import hashlib
import json
import requests
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

API_KEY = os.getenv("BITSO_API_KEY")
API_SECRET = os.getenv("BITSO_API_SECRET")

if not API_KEY or not API_SECRET:
    print("❌ Error: No se encontraron las credenciales en el archivo .env.")
    exit(1)

BASE_URL = "https://api.bitso.com"

# --- PARÁMETROS DE LA ESTRATEGIA ---
MONTO_OPERACION_MXN = 200.0       # Cantidad máxima en MXN a gastar por operación
SALDO_MINIMO_REQUERIDO = 50.0     # Mínimo en MXN para abrir nuevas compras
UMBRAL_MINIMO_GANANCIA = 1.0      # % de crecimiento de 24h mínimo para comprar

# Lista de pares permitidos contra MXN
MONEDAS_PERMITIDAS = ['btc_mxn', 'eth_mxn', 'xrp_mxn', 'sol_mxn']

def crear_firma_bitso(http_method, request_path, payload=""):
    """Genera la firma HMAC-SHA256 para autenticar peticiones en Bitso."""
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
    """Consulta los balances disponibles en tu cuenta."""
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

def escanear_mercados():
    """Obtiene y ordena los mercados de la lista permitida según su variación de 24h."""
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
                        "cripto": book.split('_')[0],
                        "precio": float(t['last']),
                        "variacion": float(t['change_24']),
                        "volumen": float(t['volume'])
                    })
            
            # Ordenar de mayor a menor rendimiento en 24 horas
            mercados_validos.sort(key=lambda x: x['variacion'], reverse=True)
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
        if resultado.get('success'):
            print(f"✅ Orden de {side.upper()} en {book.upper()} ejecutada exitosamente.")
            return True
        else:
            print(f"⚠️ Bitso rechazó la orden: {resultado.get('error')}")
    except Exception as e:
        print(f"Error crítico al enviar la orden: {e}")
    return False

def detectar_cripto_poseida(balances):
    """Identifica si el bot posee saldo en alguna cripto de la lista permitida."""
    # Equivalentes mínimos para ignorar remanentes insignificantes
    minimos = {'btc': 0.0001, 'eth': 0.001, 'xrp': 1.0, 'sol': 0.01}
    
    for cripto in ['btc', 'eth', 'xrp', 'sol']:
        saldo = balances.get(cripto, 0.0)
        umbral = minimos.get(cripto, 0.0001)
        if saldo >= umbral:
            return cripto, saldo
            
    return None, 0.0

def ciclo_principal():
    print("\n" + "="*50)
    print("--- INICIANDO CICLO DE EVALUACIÓN Y ROTACIÓN ---")
    
    balances = obtener_balances()
    mxn_disponible = balances.get('mxn', 0.0)
    print(f"💰 Saldo MXN disponible: ${mxn_disponible:,.2f}")

    # 1. Identificar si tenemos una cripto activa en nuestro portafolio
    cripto_poseida, saldo_poseido = detectar_cripto_poseida(balances)
    if cripto_poseida:
        print(f"📦 Tienes una posición activa en: {cripto_poseida.upper()} ({saldo_poseido:,.8f})")
    else:
        print("📦 No posees posiciones activas en criptomonedas.")

    # 2. Escanear el ranking de mercados
    mercados = escanear_mercados()
    if not mercados:
        print("No se pudo obtener información del mercado.")
        return
    
    mercado_lider = mercados[0]
    print(f"🏆 Mercado líder actual: {mercado_lider['book'].upper()}")
    print(f"   -> Precio: ${mercado_lider['precio']:,.2f} | Variación 24h: {mercado_lider['variacion']:+.2f}%")

    # -------------------------------------------------------------
    # ESCENARIO A: YA POSEEMOS UNA CRIPTOMONEDA (Gestión de posición)
    # -------------------------------------------------------------
    if cripto_poseida:
        book_poseido = f"{cripto_poseida}_mxn"
        
        # Buscar la información del mercado de la cripto que poseemos
        info_poseida = next((m for m in mercados if m['book'] == book_poseido), None)
        
        # Regla 1: Si la cripto poseída entra en tendencia bajista/negativa, VENDER A MXN inmediatame
        if info_poseida and info_poseida['variacion'] < 0:
            print(f"🛡️ La cripto poseída ({cripto_poseida.upper()}) cayó a variación negativa ({info_poseida['variacion']:+.2f}%). Protegiendo en MXN...")
            
            # --- DESCOMENTAR PARA REAL ---
            # ejecutar_orden(book_poseido, side="sell", tipo_monto="major", valor=saldo_poseido)
            print(f"[Simulación] Venta de {cripto_poseida.upper()} a MXN por caída de valor.")
            return

        # Regla 2: Rotación de mercado (Si la líder supera a nuestra cripto poseída)
        if mercado_lider['cripto'] != cripto_poseida and mercado_lider['variacion'] >= UMBRAL_MINIMO_GANANCIA:
            variacion_actual = info_poseida['variacion'] if info_poseida else 0.0
            print(f"🔄 ROTACIÓN DETECTADA: {mercado_lider['cripto'].upper()} ({mercado_lider['variacion']:+.2f}%) superó a tu {cripto_poseida.upper()} ({variacion_actual:+.2f}%).")
            print(f"1. Liquidadndo {cripto_poseida.upper()} a MXN...")
            
            # --- DESCOMENTAR PARA REAL ---
            # ejecutar_orden(book_poseido, side="sell", tipo_monto="major", valor=saldo_poseido)
            print(f"[Simulación] Venta de {cripto_poseida.upper()} para rotación.")

            print(f"2. Comprando {mercado_lider['book'].upper()} con los fondos en MXN...")
            # --- DESCOMENTAR PARA REAL ---
            # ejecutar_orden(mercado_lider['book'], side="buy", tipo_monto="minor", valor=MONTO_OPERACION_MXN)
            print(f"[Simulación] Compra de {mercado_lider['book'].upper()} por rotación de oportunidad.")
            return

        print(f"🟢 Manteniendo {cripto_poseida.upper()}. Sigue liderando o manteniendo buena tendencia sin ser superada.")

    # -------------------------------------------------------------
    # ESCENARIO B: NO POSEEMOS CRIPTOS (Comprar oportunamente)
    # -------------------------------------------------------------
    else:
        if mercado_lider['variacion'] >= UMBRAL_MINIMO_GANANCIA:
            if mxn_disponible >= SALDO_MINIMO_REQUERIDO:
                monto_a_gastar = min(MONTO_OPERACION_MXN, mxn_disponible)
                print(f"🚀 Comprando líder {mercado_lider['book'].upper()} (${monto_a_gastar} MXN)...")
                
                # --- DESCOMENTAR PARA REAL ---
                # ejecutar_orden(mercado_lider['book'], side="buy", tipo_monto="minor", valor=monto_a_gastar)
                print(f"[Simulación] Compra inicial de {mercado_lider['book'].upper()}.")
            else:
                print("⚪ Oportunidad detectada, pero el saldo en MXN es menor al mínimo requerido.")
        else:
            print("💤 Ningún mercado alcanza el umbral mínimo de ganancias. El capital se mantiene a salvo en MXN.")

if __name__ == "__main__":
    print("Iniciando bot con rotación automática de mercado...")
    while True:
        ciclo_principal()
        print("\n⏳ Esperando el próximo ciclo de revisión (30 minutos)...\n")
        time.sleep(1800)