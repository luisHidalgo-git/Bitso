import time

from bitso_bot.config import MODO_OPERACION
from bitso_bot.notifications import enviar_alerta_telegram
from bitso_bot.strategy import ciclo_principal


def main():
    if MODO_OPERACION == "paper":
        descripcion_modo = "simulación; no se enviarán órdenes reales"
    elif MODO_OPERACION == "safe":
        descripcion_modo = "operaciones reales con límites de riesgo"
    else:
        descripcion_modo = "operaciones reales usando el saldo disponible"

    print(f"Iniciando bot en modo {MODO_OPERACION}: {descripcion_modo}.")
    enviar_alerta_telegram(
        f"🤖 <b>Bot de Bitso iniciado en modo {MODO_OPERACION.upper()}</b>\n"
        f"• {descripcion_modo.capitalize()}."
    )
    while True:
        ciclo_principal()
        print("\n⏳ Esperando próximo ciclo de revisión (1 minuto)...\n")
        time.sleep(60)


if __name__ == "__main__":
    main()
