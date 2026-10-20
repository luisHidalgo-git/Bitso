import time

from bitso_bot.notifications import enviar_alerta_telegram
from bitso_bot.strategy import ciclo_principal


def main():
    print("Iniciando bot con logs completos en consola y alertas en Telegram...")
    enviar_alerta_telegram(
        "🤖 <b>Bot de Bitso iniciado correctamente en la nube</b> "
        "(Monitoreo activo)."
    )
    while True:
        ciclo_principal()
        print("\n⏳ Esperando próximo ciclo de revisión (1 minuto)...\n")
        time.sleep(60)


if __name__ == "__main__":
    main()
