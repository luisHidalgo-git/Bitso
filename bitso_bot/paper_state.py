import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from bitso_bot.config import COMISION_ESTIMADA_RATE, RUTA_ESTADO


@contextmanager
def _connect():
    RUTA_ESTADO.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(RUTA_ESTADO)
    try:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS bot_state "
            "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS paper_trades "
            "(timestamp TEXT NOT NULL, book TEXT NOT NULL, side TEXT NOT NULL, "
            "price REAL NOT NULL, quantity REAL NOT NULL, gross_mxn REAL NOT NULL, "
            "fee_mxn REAL NOT NULL)"
        )
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_state(key, default=None):
    with _connect() as connection:
        row = connection.execute(
            "SELECT value FROM bot_state WHERE key = ?", (key,)
        ).fetchone()
    return json.loads(row[0]) if row else default


def set_state(key, value):
    with _connect() as connection:
        connection.execute(
            "INSERT OR REPLACE INTO bot_state (key, value) VALUES (?, ?)",
            (key, json.dumps(value)),
        )


def obtener_balances_paper(capital_inicial):
    with _connect() as connection:
        row = connection.execute(
            "SELECT value FROM bot_state WHERE key = 'paper_balances'"
        ).fetchone()
        if row:
            return json.loads(row[0])

        balances = {"mxn": capital_inicial}
        connection.execute(
            "INSERT INTO bot_state (key, value) VALUES ('paper_balances', ?)",
            (json.dumps(balances),),
        )
        return balances


def ejecutar_orden_paper(book, side, tipo_monto, valor, precio):
    if valor <= 0 or precio <= 0:
        raise ValueError("El monto y el precio simulados deben ser positivos.")
    if side not in {"buy", "sell"} or tipo_monto not in {"major", "minor"}:
        raise ValueError("Tipo de orden simulada no válido.")

    currency = book.split("_", maxsplit=1)[0]
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT value FROM bot_state WHERE key = 'paper_balances'"
        ).fetchone()
        if not row:
            raise RuntimeError("El portafolio paper no ha sido inicializado.")

        balances = json.loads(row[0])
        fee_rate = COMISION_ESTIMADA_RATE
        if side == "buy" and tipo_monto == "minor":
            fee = valor * fee_rate
            total = valor + fee
            if total > balances.get("mxn", 0.0):
                return False
            quantity = valor / precio
            balances["mxn"] = balances.get("mxn", 0.0) - total
            balances[currency] = balances.get(currency, 0.0) + quantity
            gross_mxn = valor
        elif side == "sell" and tipo_monto == "major":
            quantity = valor
            if quantity > balances.get(currency, 0.0):
                return False
            gross_mxn = quantity * precio
            fee = gross_mxn * fee_rate
            balances[currency] -= quantity
            balances["mxn"] = balances.get("mxn", 0.0) + gross_mxn - fee
        else:
            raise ValueError("La moneda del monto no coincide con la acción.")

        connection.execute(
            "INSERT OR REPLACE INTO bot_state (key, value) VALUES "
            "('paper_balances', ?)",
            (json.dumps(balances),),
        )
        connection.execute(
            "INSERT INTO paper_trades "
            "(timestamp, book, side, price, quantity, gross_mxn, fee_mxn) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                book,
                side,
                precio,
                quantity,
                gross_mxn,
                fee,
            ),
        )
    return True
