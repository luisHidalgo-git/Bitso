from bitso_bot.bitso_api import escanear_mercados, obtener_balances
from bitso_bot.config import (
    PORCENTAJE_TRAILING_STOP,
    SALDO_MINIMO_REQUERIDO,
    UMBRAL_DIFERENCIA_ROTACION,
    UMBRAL_MINIMO_GANANCIA,
)
from bitso_bot.notifications import enviar_alerta_telegram

ESTADO_POSICION = {
    "cripto_actual": None,
    "precio_maximo_alcanzado": 0.0
}


def detectar_cripto_poseida(balances):
    """Identifica si hay saldo activo en alguna de las criptos permitidas."""
    minimos = {"btc": 0.0001, "eth": 0.001, "xrp": 1.0, "sol": 0.01}

    for cripto in ["btc", "eth", "xrp", "sol"]:
        saldo = balances.get(cripto, 0.0)
        umbral = minimos.get(cripto, 0.0001)
        if saldo >= umbral:
            return cripto, saldo

    return None, 0.0


def ciclo_principal():
    print("\n" + "=" * 50)
    print("--- EVALUANDO MERCADO (CONSOLA & TELEGRAM) ---")

    balances = obtener_balances()
    mxn_disponible = balances.get("mxn", 0.0)
    print(f"💰 Saldo MXN total disponible: ${mxn_disponible:,.2f}")

    cripto_poseida, saldo_poseido = detectar_cripto_poseida(balances)

    if not cripto_poseida:
        ESTADO_POSICION["cripto_actual"] = None
        ESTADO_POSICION["precio_maximo_alcanzado"] = 0.0
        print("📦 No hay posiciones activas en cripto.")
    else:
        print(f"📦 Posición activa: {cripto_poseida.upper()} ({saldo_poseido:,.8f})")

    mercados = escanear_mercados()
    if not mercados:
        print("No se pudo obtener información del mercado.")
        return

    mercado_lider = mercados[0]
    print(f"🏆 Mercado líder actual: {mercado_lider['book'].upper()}")
    print(
        f"   -> Precio: ${mercado_lider['precio']:,.2f} | "
        f"Variación 24h: {mercado_lider['variacion']:+.2f}%"
    )

    if cripto_poseida:
        book_poseido = f"{cripto_poseida}_mxn"
        info_poseida = next(
            (mercado for mercado in mercados if mercado["book"] == book_poseido),
            None
        )

        if not info_poseida:
            return

        precio_actual = info_poseida["precio"]
        variacion_poseida = info_poseida["variacion"]

        if ESTADO_POSICION["cripto_actual"] != cripto_poseida:
            ESTADO_POSICION["cripto_actual"] = cripto_poseida
            ESTADO_POSICION["precio_maximo_alcanzado"] = precio_actual
            print(
                f"📈 [Trailing Stop] Nueva posición registrada. "
                f"Precio base inicial: ${precio_actual:,.2f}"
            )
        elif precio_actual > ESTADO_POSICION["precio_maximo_alcanzado"]:
            ESTADO_POSICION["precio_maximo_alcanzado"] = precio_actual
            print(
                f"🚀 [Trailing Stop] ¡Nuevo pico máximo para "
                f"{cripto_poseida.upper()}! -> ${precio_actual:,.2f}"
            )

        precio_limite_venta = ESTADO_POSICION["precio_maximo_alcanzado"] * (
            1 - (PORCENTAJE_TRAILING_STOP / 100)
        )
        print(
            f"🛡️ [Trailing Stop] Pico: "
            f"${ESTADO_POSICION['precio_maximo_alcanzado']:,.2f} | "
            f"Límite dinámico: ${precio_limite_venta:,.2f}"
        )

        if precio_actual <= precio_limite_venta or variacion_poseida < 0:
            enviar_alerta_telegram(
                f"🛡️ <b>Protección activada (Trailing Stop / Caída)</b>\n"
                f"• Vendiendo {cripto_poseida.upper()} a MXN.\n"
                f"• Precio actual: ${precio_actual:,.2f} | "
                f"Pico: ${ESTADO_POSICION['precio_maximo_alcanzado']:,.2f}"
            )

            # --- DESCOMENTAR PARA OPERAR CON DINERO REAL ---
            ejecutar_orden(book_poseido, side="sell", tipo_monto="major", valor=saldo_poseido)
            # print(f"[Simulación] Venta del 100% de {cripto_poseida.upper()} ejecutada.")

            ESTADO_POSICION["cripto_actual"] = None
            ESTADO_POSICION["precio_maximo_alcanzado"] = 0.0
            return

        if mercado_lider["cripto"] != cripto_poseida:
            diferencia_rendimiento = (
                mercado_lider["variacion"] - variacion_poseida
            )
            print(
                f"📊 Comparativa: Líder {mercado_lider['cripto'].upper()} "
                f"({mercado_lider['variacion']:+.2f}%) vs Tu "
                f"{cripto_poseida.upper()} ({variacion_poseida:+.2f}%)"
            )
            print(
                f"   -> Ventaja del líder: +{diferencia_rendimiento:.2f}% "
                f"(Requerido para rotar: +{UMBRAL_DIFERENCIA_ROTACION:.2f}%)"
            )

            if diferencia_rendimiento >= UMBRAL_DIFERENCIA_ROTACION:
                enviar_alerta_telegram(
                    f"🔄 <b>Rotación de Mercado Detectada</b>\n"
                    f"• Vendiendo {cripto_poseida.upper()} "
                    f"({variacion_poseida:+.2f}%)\n"
                    f"• Comprando líder: {mercado_lider['book'].upper()} "
                    f"({mercado_lider['variacion']:+.2f}%)"
                )

                # --- DESCOMENTAR PARA OPERAR CON DINERO REAL ---
                ejecutar_orden(book_poseido, side="sell", tipo_monto="major", valor=saldo_poseido)
                balances_recientes = obtener_balances()
                mxn_a_reinvertir = balances_recientes.get('mxn', 0.0)
                ejecutar_orden(mercado_lider['book'], side="buy", tipo_monto="minor", valor=mxn_a_reinvertir)
                print(
                    # f"[Simulación] Rotación completada hacia "
                    f"{mercado_lider['book'].upper()}."
                )

                ESTADO_POSICION["cripto_actual"] = None
                ESTADO_POSICION["precio_maximo_alcanzado"] = 0.0
                return

            print(f"💡 No conviene rotar aún. Se mantiene {cripto_poseida.upper()}.")
            return

        print(f"🟢 Manteniendo {cripto_poseida.upper()} dentro del margen seguro.")

    else:
        if mercado_lider["variacion"] >= UMBRAL_MINIMO_GANANCIA:
            if mxn_disponible >= SALDO_MINIMO_REQUERIDO:
                monto_a_gastar = mxn_disponible
                enviar_alerta_telegram(
                    f"🚀 <b>Nueva Compra Inicial</b>\n"
                    f"• Activo: {mercado_lider['book'].upper()}\n"
                    f"• Monto: ${monto_a_gastar:,.2f} MXN\n"
                    f"• Variación 24h: {mercado_lider['variacion']:+.2f}%"
                )

                # --- DESCOMENTAR PARA OPERAR CON DINERO REAL ---
                ejecutar_orden(mercado_lider['book'], side="buy", tipo_monto="minor", valor=monto_a_gastar)
                print(
                    # f"[Simulación] Compra inicial del 100% del capital en "
                    f"{mercado_lider['book'].upper()}."
                )
            else:
                print(
                    "⚪ Oportunidad detectada, pero el saldo en MXN es menor "
                    "al mínimo requerido."
                )
        else:
            print(
                "💤 Ningún mercado supera el umbral de compra. "
                "El dinero se queda 100% a salvo en MXN."
            )
