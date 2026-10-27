import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BITSO_API_KEY")
API_SECRET = os.getenv("BITSO_API_SECRET")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MODO_OPERACION = os.getenv("MODO_OPERACION", "paper").strip().lower()
MODOS_OPERACION_VALIDOS = {"paper", "safe", "full"}
if MODO_OPERACION not in MODOS_OPERACION_VALIDOS:
    raise ValueError(
        "MODO_OPERACION debe ser uno de estos valores: paper, safe o full."
    )

if MODO_OPERACION in {"safe", "full"} and (not API_KEY or not API_SECRET):
    raise SystemExit(
        "❌ Para operar en vivo, configura BITSO_API_KEY y BITSO_API_SECRET."
    )

BASE_URL = "https://api.bitso.com"

SALDO_MINIMO_REQUERIDO = 50.0
UMBRAL_MINIMO_GANANCIA = 2.0
UMBRAL_DIFERENCIA_ROTACION = 3.5
PORCENTAJE_TRAILING_STOP = 5.0
STOP_LOSS_ESTIMADO_PORCENTAJE = 4.0

MAX_EXPOSICION_PORCENTAJE = 5.0
RIESGO_MAXIMO_OPERACION_PORCENTAJE = 0.5
VOLUMEN_MINIMO_MXN = 50_000.0

COMISION_ESTIMADA_RATE = 0.005
try:
    CAPITAL_INICIAL_PAPER = float(os.getenv("CAPITAL_INICIAL_PAPER", "1000"))
except ValueError as error:
    raise ValueError("CAPITAL_INICIAL_PAPER debe ser un número.") from error
if CAPITAL_INICIAL_PAPER <= 0:
    raise ValueError("CAPITAL_INICIAL_PAPER debe ser mayor que cero.")

RUTA_ESTADO = Path(
    os.getenv(
        "RUTA_ESTADO",
        str(Path(__file__).resolve().parent.parent / "data" / "paper_state.sqlite3"),
    )
)

MONEDAS_PERMITIDAS = ["btc_mxn", "eth_mxn", "xrp_mxn", "sol_mxn"]
