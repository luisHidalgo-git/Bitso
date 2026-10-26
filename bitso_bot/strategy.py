from bitso_bot import paper_state
from bitso_bot.bitso_api import ejecutar_orden, escanear_mercados, obtener_balances
from bitso_bot.config import (
    CAPITAL_INICIAL_PAPER,
    MAX_EXPOSICION_PORCENTAJE,
    MODO_OPERACION,
    PORCENTAJE_TRAILING_STOP,
    RIESGO_MAXIMO_OPERACION_PORCENTAJE,
    SALDO_MINIMO_REQUERIDO,
    STOP_LOSS_ESTIMADO_PORCENTAJE,
    UMBRAL_DIFERENCIA_ROTACION,
    UMBRAL_MINIMO_GANANCIA,
    VOLUMEN_MINIMO_MXN,
)
from bitso_bot.notifications import enviar_alerta_telegram

ESTADO_POSICION = {
    "cripto_actual": None,
    "precio_maximo_alcanzado": 0.0,
}

UMBRALES_POSICION = {"btc": 0.0001, "eth": 0.001, "xrp": 1.0, "sol": 0.01}


def _persistir_estado_posicion():
    return MODO_OPERACION in {"paper", "safe"}


def _clave_estado_posicion():
    return "position" if MODO_OPERACION == "paper" else "safe_position"


def detectar_cripto_poseida(balances, estado_registrado=None):
    """Identifica una posición única; admite posiciones pequeñas registradas."""
    posiciones = []
    cripto_registrada = (
        estado_registrado.get("crypto") if estado_registrado else None
    )

    for cripto, umbral in UMBRALES_POSICION.items():
        saldo = balances.get(cripto, 0.0)
        if saldo >= umbral or (cripto == cripto_registrada and saldo > 0):
            posiciones.append((cripto, saldo))

    if len(posiciones) > 1:
        raise ValueError(
            "Se detectaron varias posiciones en criptomonedas; "
            "el bot solo puede gestionar una a la vez."
        )
    return posiciones[0] if posiciones else (None, 0.0)


def calcular_monto_compra(saldo_disponible, capital_total):
    """Calcula una compra con límites de exposición y riesgo estimado."""
    if saldo_disponible <= 0 or capital_total <= 0:
        return 0.0

    limite_exposicion = capital_total * MAX_EXPOSICION_PORCENTAJE / 100
    limite_riesgo = (
        capital_total
        * RIESGO_MAXIMO_OPERACION_PORCENTAJE
        / 100
        / (STOP_LOSS_ESTIMADO_PORCENTAJE / 100)
    )
    return min(saldo_disponible, limite_exposicion, limite_riesgo)


def _mercado_apto_para_compra(mercado, mercados):
    """Filtra tendencias débiles y mercados con poco volumen negociado."""
    variaciones = {
        item["cripto"]: item["variacion"]
        for item in mercados
        if item["cripto"] in {"btc", "eth"}
    }
    return (
        variaciones.get("btc", 0) > 0
        and variaciones.get("eth", 0) > 0
        and mercado["variacion"] >= UMBRAL_MINIMO_GANANCIA
        and mercado["precio"] * mercado["volumen"] >= VOLUMEN_MINIMO_MXN
    )


def _obtener_balances():
    if MODO_OPERACION == "paper":
        return paper_state.obtener_balances_paper(CAPITAL_INICIAL_PAPER)
    return obtener_balances()


def _capital_total(balances, mercados):
    precios = {mercado["cripto"]: mercado["precio"] for mercado in mercados}
    return balances.get("mxn", 0.0) + sum(
        balances.get(cripto, 0.0) * precios.get(cripto, 0.0)
        for cripto in UMBRALES_POSICION
    )


def _monto_compra(saldo_disponible, balances, mercados):
    if MODO_OPERACION == "full":
        return saldo_disponible
    return calcular_monto_compra(
        saldo_disponible,
        _capital_total(balances, mercados),
    )


def _compra_permitida(mercado, mercados):
    return MODO_OPERACION == "full" or _mercado_apto_para_compra(mercado, mercados)


def _ejecutar_orden(book, side, tipo_monto, valor, precio):
    if MODO_OPERACION != "paper":
        return ejecutar_orden(
            book,
            side=side,
            tipo_monto=tipo_monto,
            valor=valor,
        )

    aceptada = paper_state.ejecutar_orden_paper(
        book,
        side,
        tipo_monto,
        valor,
        precio,
    )
    if aceptada:
        enviar_alerta_telegram(
            f"🧪 <b>Orden simulada</b>\n"
            f"• Acción: {side.upper()}\n• Mercado: {book.upper()}"
        )
    else:
        print("⚠️ Orden simulada omitida: saldo insuficiente.")
    return aceptada


def _registrar_posicion(crypto, price):
    ESTADO_POSICION["cripto_actual"] = crypto
    ESTADO_POSICION["precio_maximo_alcanzado"] = price
    if _persistir_estado_posicion():
        estado_anterior = paper_state.get_state(_clave_estado_posicion()) or {}
        if estado_anterior.get("crypto") != crypto:
            estado_anterior = {}
        paper_state.set_state(
            _clave_estado_posicion(),
            {
                "crypto": crypto,
                "entry_price": estado_anterior.get("entry_price", price),
                "highest_price": max(
                    price,
                    estado_anterior.get("highest_price", 0.0),
                ),
            },
        )


def _limpiar_posicion():
    ESTADO_POSICION["cripto_actual"] = None
    ESTADO_POSICION["precio_maximo_alcanzado"] = 0.0
    if _persistir_estado_posicion():
        paper_state.set_state(_clave_estado_posicion(), None)


def ciclo_principal():
    print("\n" + "=" * 50)
    print(f"--- EVALUANDO MERCADO (MODO {MODO_OPERACION.upper()}) ---")

    balances = _obtener_balances()
    mxn_disponible = balances.get("mxn", 0.0)
    print(f"💰 Saldo MXN disponible: ${mxn_disponible:,.2f}")

    estado_registrado = (
        paper_state.get_state(_clave_estado_posicion())
        if _persistir_estado_posicion()
        else None
    )
    cripto_poseida, saldo_poseido = detectar_cripto_poseida(
        balances,
        estado_registrado,
    )
    if not cripto_poseida:
        _limpiar_posicion()
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
            None,
        )
        if not info_poseida:
            print(f"⚠️ No se encontró el mercado para {cripto_poseida.upper()}.")
            return

        precio_actual = info_poseida["precio"]
        variacion_poseida = info_poseida["variacion"]
        estado_persistido = estado_registrado or {}
        precio_maximo_guardado = estado_persistido.get("highest_price", 0.0)

        if ESTADO_POSICION["cripto_actual"] != cripto_poseida:
            precio_maximo = max(
                precio_actual,
                precio_maximo_guardado,
            )
            _registrar_posicion(cripto_poseida, precio_maximo)
            print(
                f"📈 [Trailing Stop] Posición registrada. Precio base: "
                f"${precio_maximo:,.2f}"
            )
        elif precio_actual > ESTADO_POSICION["precio_maximo_alcanzado"]:
            ESTADO_POSICION["precio_maximo_alcanzado"] = precio_actual
            if _persistir_estado_posicion():
                _registrar_posicion(cripto_poseida, precio_actual)
            print(
                f"🚀 [Trailing Stop] Nuevo pico para {cripto_poseida.upper()}: "
                f"${precio_actual:,.2f}"
            )

        precio_limite_venta = ESTADO_POSICION["precio_maximo_alcanzado"] * (
            1 - PORCENTAJE_TRAILING_STOP / 100
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
            if _ejecutar_orden(
                book_poseido,
                "sell",
                "major",
                saldo_poseido,
                precio_actual,
            ):
                _limpiar_posicion()
            return

        if mercado_lider["cripto"] != cripto_poseida:
            diferencia_rendimiento = (
                mercado_lider["variacion"] - variacion_poseida
            )
            print(
                f"📊 Comparativa: líder {mercado_lider['cripto'].upper()} "
                f"({mercado_lider['variacion']:+.2f}%) vs posición "
                f"{cripto_poseida.upper()} ({variacion_poseida:+.2f}%)"
            )
            print(
                f"   -> Ventaja: +{diferencia_rendimiento:.2f}% "
                f"(requerido: +{UMBRAL_DIFERENCIA_ROTACION:.2f}%)"
            )

            if diferencia_rendimiento >= UMBRAL_DIFERENCIA_ROTACION:
                enviar_alerta_telegram(
                    f"🔄 <b>Rotación de mercado detectada</b>\n"
                    f"• Vendiendo {cripto_poseida.upper()}.\n"
                    f"• Comprando líder: {mercado_lider['book'].upper()}."
                )
                if not _ejecutar_orden(
                    book_poseido,
                    "sell",
                    "major",
                    saldo_poseido,
                    precio_actual,
                ):
                    return

                _limpiar_posicion()
                balances_recientes = _obtener_balances()
                mxn_a_reinvertir = _monto_compra(
                    balances_recientes.get("mxn", 0.0),
                    balances_recientes,
                    mercados,
                )
                if (
                    mxn_a_reinvertir >= SALDO_MINIMO_REQUERIDO
                    and _compra_permitida(mercado_lider, mercados)
                    and _ejecutar_orden(
                        mercado_lider["book"],
                        "buy",
                        "minor",
                        mxn_a_reinvertir,
                        mercado_lider["precio"],
                    )
                ):
                    _registrar_posicion(
                        mercado_lider["cripto"],
                        mercado_lider["precio"],
                    )
                    print(
                        f"✅ Rotación completada hacia "
                        f"{mercado_lider['book'].upper()} por "
                        f"${mxn_a_reinvertir:,.2f} MXN."
                    )
                return

            print(f"💡 No conviene rotar aún. Se mantiene {cripto_poseida.upper()}.")
            return

        print(f"🟢 Manteniendo {cripto_poseida.upper()} dentro del margen seguro.")
        return

    if mercado_lider["variacion"] >= UMBRAL_MINIMO_GANANCIA:
        if not _compra_permitida(mercado_lider, mercados):
            print("⚪ Compra omitida: tendencia o volumen insuficiente.")
            return

        monto_a_gastar = _monto_compra(mxn_disponible, balances, mercados)
        if monto_a_gastar >= SALDO_MINIMO_REQUERIDO:
            enviar_alerta_telegram(
                f"🚀 <b>Nueva compra ({MODO_OPERACION.upper()})</b>\n"
                f"• Activo: {mercado_lider['book'].upper()}\n"
                f"• Monto: ${monto_a_gastar:,.2f} MXN\n"
                f"• Variación 24h: {mercado_lider['variacion']:+.2f}%"
            )
            if _ejecutar_orden(
                mercado_lider["book"],
                "buy",
                "minor",
                monto_a_gastar,
                mercado_lider["precio"],
            ):
                _registrar_posicion(
                    mercado_lider["cripto"],
                    mercado_lider["precio"],
                )
                print(
                    f"✅ Compra de {mercado_lider['book'].upper()} por "
                    f"${monto_a_gastar:,.2f} MXN."
                )
        else:
            print(
                "⚪ Oportunidad detectada, pero el monto disponible queda "
                f"por debajo del mínimo de ${SALDO_MINIMO_REQUERIDO:.2f} MXN."
            )
    else:
        print(
            "💤 Ningún mercado supera el umbral de compra. "
            "El dinero se queda en MXN."
        )
