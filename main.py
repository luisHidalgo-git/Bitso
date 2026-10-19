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

# Credenciales de Telegram (opcionales)
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not API_KEY or not API_SECRET:
    print("❌ Error: No se encontraron las credenciales de Bitso en el archivo .env.")
    exit(1)

BASE_URL = "https://api.bitso.com"

# --- PARÁMETROS DE LA ESTRATEGIA ---
SALDO_MINIMO_REQUERIDO = 50.0        # Mínimo en MXN para abrir compras
UMBRAL_MINIMO_GANANCIA = 1.0         # % mínimo de crecimiento 24h para comprar desde MXN
UMBRAL_DIFERENCIA_ROTACION = 2.5     # % EXTRA que debe superar la nueva moneda para rotar

# --- TRAILING STOP (Protección de Ganancias) ---
PORCENTAJE_TRAILING_STOP = 1.5       # Caída del 1.5% desde el pico máximo dispara la venta

# Estado dinámico de la posición activa
ESTADO_POSICION = {
    "cripto_actual": None,
    "precio_maximo_alcanzado": 0.0
}

MONEDAS_PERMITIDAS = ['btc_mxn', 'eth_mxn', 'xrp_mxn', 'sol_mxn']

def enviar_alerta_telegram(mensaje):
    """Envía una notificación push a tu Telegram y también imprime en consola."""
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

def crear_firma_bitso(http_method, request_path, payload=""):
    """Genera la firma HMAC-SHA256 requerida por Bitso."""
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
    """Consulta los balances disponibles en tu cuenta de Bitso."""
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
    """Obtiene y ordena los mercados según su variación de 24h."""
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
            enviar_alerta_telegram(f"✅ <b>Orden ejecutada con éxito</b>\n• Acción: {side.upper()}\n• Mercado: {book.upper()}")
            return True
        else:
            enviar_alerta_telegram(f"⚠️ <b>Bitso rechazó la orden</b>\n• Mercado: {book.upper()}\n• Motivo: {resultado.get('error')}")
    except Exception as e:
        enviar_alerta_telegram(f"❌ <b>Error crítico al enviar orden</b> en {book.upper()}: {e}")
    return False

def detectar_cripto_poseida(balances):
    """Identifica si tenemos saldo activo en alguna de las criptos permitidas."""
    minimos = {'btc': 0.0001, 'eth': 0.001, 'xrp': 1.0, 'sol': 0.01}
    
    for cripto in ['btc', 'eth', 'xrp', 'sol']:
        saldo = balances.get(cripto, 0.0)
        umbral = minimos.get(cripto, 0.0001)
        if saldo >= umbral:
            return cripto, saldo
            
    return None, 0.0

def ciclo_principal():
    global ESTADO_POSICION
    
    print("\n" + "="*50)
    print("--- EVALUANDO MERCADO (CONSOLA & TELEGRAM) ---")
    
    balances = obtener_balances()
    mxn_disponible = balances.get('mxn', 0.0)
    print(f"💰 Saldo MXN total disponible: ${mxn_disponible:,.2f}")

    # 1. Identificar si ya tenemos cripto en portafolio
    cripto_poseida, saldo_poseido = detectar_cripto_poseida(balances)
    
    if not cripto_poseida:
        ESTADO_POSICION["cripto_actual"] = None
        ESTADO_POSICION["precio_maximo_alcanzado"] = 0.0
        print("📦 No hay posiciones activas en cripto.")
    else:
        print(f"📦 Posición activa: {cripto_poseida.upper()} ({saldo_poseido:,.8f})")

    # 2. Escanear mercados
    mercados = escanear_mercados()
    if not mercados:
        print("No se pudo obtener información del mercado.")
        return
    
    mercado_lider = mercados[0]
    print(f"🏆 Mercado líder actual: {mercado_lider['book'].upper()}")
    print(f"   -> Precio: ${mercado_lider['precio']:,.2f} | Variación 24h: {mercado_lider['variacion']:+.2f}%")

    # -------------------------------------------------------------
    # ESCENARIO A: YA TENEMOS UNA CRIPTO COMPRADA
    # -------------------------------------------------------------
    if cripto_poseida:
        book_poseido = f"{cripto_poseida}_mxn"
        info_poseida = next((m for m in mercados if m['book'] == book_poseido), None)
        
        if not info_poseida:
            return

        precio_actual = info_poseida['precio']
        variacion_poseida = info_poseida['variacion']

        # Rastreador de pico máximo para Trailing Stop
        if ESTADO_POSICION["cripto_actual"] != cripto_poseida:
            ESTADO_POSICION["cripto_actual"] = cripto_poseida
            ESTADO_POSICION["precio_maximo_alcanzado"] = precio_actual
            print(f"📈 [Trailing Stop] Nueva posición registrada. Precio base inicial: ${precio_actual:,.2f}")
        else:
            if precio_actual > ESTADO_POSICION["precio_maximo_alcanzado"]:
                ESTADO_POSICION["precio_maximo_alcanzado"] = precio_actual
                print(f"🚀 [Trailing Stop] ¡Nuevo pico máximo para {cripto_poseida.upper()}! -> ${precio_actual:,.2f}")

        precio_limite_venta = ESTADO_POSICION["precio_maximo_alcanzado"] * (1 - (PORCENTAJE_TRAILING_STOP / 100))
        print(f"🛡️ [Trailing Stop] Pico: ${ESTADO_POSICION['precio_maximo_alcanzado']:,.2f} | Límite dinámico: ${precio_limite_venta:,.2f}")

        # REGLA 1: Trailing Stop o Caída Negativa
        if precio_actual <= precio_limite_venta or variacion_poseida < 0:
            enviar_alerta_telegram(f"🛡️ <b>Protección activada (Trailing Stop / Caída)</b>\n• Vendiendo {cripto_poseida.upper()} a MXN.\n• Precio actual: ${precio_actual:,.2f} | Pico: ${ESTADO_POSICION['precio_maximo_alcanzado']:,.2f}")
            
            # --- DESCOMENTAR PARA OPERAR CON DINERO REAL ---
            # ejecutar_orden(book_poseido, side="sell", tipo_monto="major", valor=saldo_poseido)
            print(f"[Simulación] Venta del 100% de {cripto_poseida.upper()} ejecutada.")
            
            ESTADO_POSICION["cripto_actual"] = None
            ESTADO_POSICION["precio_maximo_alcanzado"] = 0.0
            return

        # REGLA 2: Rotación Inteligente
        if mercado_lider['cripto'] != cripto_poseida:
            diferencia_rendimiento = mercado_lider['variacion'] - variacion_poseida
            print(f"📊 Comparativa: Líder {mercado_lider['cripto'].upper()} ({mercado_lider['variacion']:+.2f}%) vs Tu {cripto_poseida.upper()} ({variacion_poseida:+.2f}%)")
            print(f"   -> Ventaja del líder: +{diferencia_rendimiento:.2f}% (Requerido para rotar: +{UMBRAL_DIFERENCIA_ROTACION:.2f}%)")

            if diferencia_rendimiento >= UMBRAL_DIFERENCIA_ROTACION:
                enviar_alerta_telegram(f"🔄 <b>Rotación de Mercado Detectada</b>\n• Vendiendo {cripto_poseida.upper()} ({variacion_poseida:+.2f}%)\n• Comprando líder: {mercado_lider['book'].upper()} ({mercado_lider['variacion']:+.2f}%)")
                
                # --- DESCOMENTAR PARA OPERAR CON DINERO REAL ---
                # ejecutar_orden(book_poseido, side="sell", tipo_monto="major", valor=saldo_poseido)
                # balances_recientes = obtener_balances()
                # mxn_a_reinvertir = balances_recientes.get('mxn', 0.0)
                # ejecutar_orden(mercado_lider['book'], side="buy", tipo_monto="minor", valor=mxn_a_reinvertir)
                print(f"[Simulación] Rotación completada hacia {mercado_lider['book'].upper()}.")
                
                ESTADO_POSICION["cripto_actual"] = None
                ESTADO_POSICION["precio_maximo_alcanzado"] = 0.0
                return
            else:
                print(f"💡 No conviene rotar aún. Se mantiene {cripto_poseida.upper()}.")
                return

        print(f"🟢 Manteniendo {cripto_poseida.upper()} dentro del margen seguro.")

    # -------------------------------------------------------------
    # ESCENARIO B: NO TENEMOS CRIPTOS (Invertir todo el saldo MXN)
    # -------------------------------------------------------------
    else:
        if mercado_lider['variacion'] >= UMBRAL_MINIMO_GANANCIA:
            if mxn_disponible >= SALDO_MINIMO_REQUERIDO:
                monto_a_gastar = mxn_disponible
                enviar_alerta_telegram(f"🚀 <b>Nueva Compra Inicial</b>\n• Activo: {mercado_lider['book'].upper()}\n• Monto: ${monto_a_gastar:,.2f} MXN\n• Variación 24h: {mercado_lider['variacion']:+.2f}%")
                
                # --- DESCOMENTAR PARA OPERAR CON DINERO REAL ---
                # ejecutar_orden(mercado_lider['book'], side="buy", tipo_monto="minor", valor=monto_a_gastar)
                print(f"[Simulación] Compra inicial del 100% del capital en {mercado_lider['book'].upper()}.")
            else:
                print("⚪ Oportunidad detectada, pero el saldo en MXN es menor al mínimo requerido.")
        else:
            print("💤 Ningún mercado supera el umbral de compra. El dinero se queda 100% a salvo en MXN.")

if __name__ == "__main__":
    print("Iniciando bot con logs completos en consola y alertas en Telegram...")
    enviar_alerta_telegram("🤖 <b>Bot de Bitso iniciado correctamente en la nube</b> (Monitoreo activo).")
    while True:
        ciclo_principal()
        print("\n⏳ Esperando próximo ciclo de revisión (30 minutos)...\n")
        time.sleep(60)