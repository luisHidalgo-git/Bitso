import os

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BITSO_API_KEY")
API_SECRET = os.getenv("BITSO_API_SECRET")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not API_KEY or not API_SECRET:
    print("❌ Error: No se encontraron las credenciales de Bitso en el archivo .env.")
    raise SystemExit(1)

BASE_URL = "https://api.bitso.com"

SALDO_MINIMO_REQUERIDO = 50.0
UMBRAL_MINIMO_GANANCIA = 1.0
UMBRAL_DIFERENCIA_ROTACION = 2.5
PORCENTAJE_TRAILING_STOP = 1.5

MONEDAS_PERMITIDAS = ["btc_mxn", "eth_mxn", "xrp_mxn", "sol_mxn"]
