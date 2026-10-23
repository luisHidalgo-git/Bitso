import time

from bitso_bot.notifications import enviar_alerta_telegram
from bitso_bot.strategy import ciclo_principal


def main():
    print(
        "Iniciando bot con operaciones reales habilitadas, "
        "logs en consola y alertas en Telegram..."
    )
    enviar_alerta_telegram(
        "🤖 <b>Bot de Bitso iniciado con operaciones reales habilitadas</b> "
        "(Monitoreo activo)."
    )
    while True:
        ciclo_principal()
        print("\n⏳ Esperando próximo ciclo de revisión (1 minuto)...\n")
        time.sleep(60)


if __name__ == "__main__":
    main()
