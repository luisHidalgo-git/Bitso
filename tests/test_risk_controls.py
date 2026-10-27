import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bitso_bot import paper_state
from bitso_bot.config import (
    MAX_EXPOSICION_PORCENTAJE,
    PORCENTAJE_TRAILING_STOP,
    RIESGO_MAXIMO_OPERACION_PORCENTAJE,
    STOP_LOSS_ESTIMADO_PORCENTAJE,
    UMBRAL_DIFERENCIA_ROTACION,
    UMBRAL_MINIMO_GANANCIA,
    VOLUMEN_MINIMO_MXN,
)
from bitso_bot.strategy import (
    _debe_vender,
    _mercado_apto_para_compra,
    _monto_compra,
    calcular_monto_compra,
    ciclo_principal,
    detectar_cripto_poseida,
)


class RiskControlTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = paper_state.RUTA_ESTADO
        paper_state.RUTA_ESTADO = Path(self.temp_dir.name) / "test.sqlite3"

    def tearDown(self):
        paper_state.RUTA_ESTADO = self.original_db_path
        self.temp_dir.cleanup()

    def test_buy_size_obeys_exposure_and_risk_caps(self):
        amount = calcular_monto_compra(1000, 1000)
        self.assertAlmostEqual(
            amount,
            1000 * MAX_EXPOSICION_PORCENTAJE / 100,
        )
        risk_cap = (
            1000
            * RIESGO_MAXIMO_OPERACION_PORCENTAJE
            / 100
            / (STOP_LOSS_ESTIMADO_PORCENTAJE / 100)
        )
        self.assertLessEqual(amount, risk_cap)

    def test_safe_and_full_modes_use_different_buy_limits(self):
        balances = {"mxn": 1000}
        markets = [{"cripto": "btc", "precio": 2_000_000}]
        with patch("bitso_bot.strategy.MODO_OPERACION", "safe"):
            self.assertEqual(_monto_compra(1000, balances, markets), 50)
        with patch("bitso_bot.strategy.MODO_OPERACION", "full"):
            self.assertEqual(_monto_compra(1000, balances, markets), 1000)

    def test_strategy_defaults_are_more_conservative(self):
        self.assertEqual(MAX_EXPOSICION_PORCENTAJE, 5.0)
        self.assertEqual(RIESGO_MAXIMO_OPERACION_PORCENTAJE, 0.5)
        self.assertEqual(UMBRAL_MINIMO_GANANCIA, 2.0)
        self.assertEqual(UMBRAL_DIFERENCIA_ROTACION, 3.5)
        self.assertEqual(PORCENTAJE_TRAILING_STOP, 5.0)

    def test_exit_rules_trigger_entry_stop_and_trailing_stop(self):
        self.assertTrue(
            _debe_vender(
                95,
                100,
                100,
                1,
            )
        )
        self.assertTrue(
            _debe_vender(
                94,
                100,
                105,
                1,
            )
        )
        self.assertFalse(
            _debe_vender(
                98,
                100,
                100,
                1,
            )
        )

    def test_paper_orders_persist_balances_and_charge_fees(self):
        balances = paper_state.obtener_balances_paper(1000)
        self.assertEqual(balances, {"mxn": 1000})
        self.assertTrue(
            paper_state.ejecutar_orden_paper("btc_mxn", "buy", "minor", 100, 100)
        )
        balances = paper_state.obtener_balances_paper(0)
        self.assertAlmostEqual(balances["mxn"], 899.5)
        self.assertAlmostEqual(balances["btc"], 1)
        self.assertTrue(
            paper_state.ejecutar_orden_paper("btc_mxn", "sell", "major", 1, 110)
        )
        balances = paper_state.obtener_balances_paper(0)
        self.assertAlmostEqual(balances["mxn"], 1008.95)
        self.assertAlmostEqual(balances["btc"], 0)
        with sqlite3.connect(paper_state.RUTA_ESTADO) as connection:
            trade_count = connection.execute(
                "SELECT COUNT(*) FROM paper_trades"
            ).fetchone()[0]
        self.assertEqual(trade_count, 2)

    def test_buy_filter_requires_positive_btc_eth_and_volume(self):
        markets = [
            {"cripto": "btc", "variacion": 0.1, "precio": 1, "volumen": 1},
            {"cripto": "eth", "variacion": 0.1, "precio": 1, "volumen": 1},
            {
                "cripto": "sol",
                "variacion": 3,
                "precio": VOLUMEN_MINIMO_MXN,
                "volumen": 1,
            },
        ]
        self.assertTrue(_mercado_apto_para_compra(markets[-1], markets))
        markets[0]["variacion"] = 0
        self.assertFalse(_mercado_apto_para_compra(markets[-1], markets))

    def test_multiple_existing_positions_are_rejected(self):
        with self.assertRaises(ValueError):
            detectar_cripto_poseida({"btc": 0.001, "eth": 0.01})

    def test_registered_position_is_detected_below_balance_threshold(self):
        position, amount = detectar_cripto_poseida(
            {"btc": 0.00005},
            {"crypto": "btc", "entry_price": 2_000_000, "highest_price": 2_000_000},
        )
        self.assertEqual(position, "btc")
        self.assertEqual(amount, 0.00005)

    def test_paper_cycle_does_not_call_live_balance_or_order_api(self):
        markets = [
            {
                "book": "btc_mxn",
                "cripto": "btc",
                "precio": 2_000_000,
                "variacion": 2,
                "volumen": 1,
            },
            {
                "book": "eth_mxn",
                "cripto": "eth",
                "precio": 100_000,
                "variacion": 1,
                "volumen": 10,
            },
        ]
        with patch("bitso_bot.strategy.MODO_OPERACION", "paper"):
            with patch(
                "bitso_bot.strategy.escanear_mercados", return_value=markets
            ):
                with patch(
                    "bitso_bot.strategy.enviar_alerta_telegram"
                ):
                    with patch(
                        "bitso_bot.strategy.obtener_balances",
                        side_effect=AssertionError(
                            "paper must not read live balances"
                        ),
                    ):
                        with patch(
                            "bitso_bot.strategy.ejecutar_orden",
                            side_effect=AssertionError(
                                "paper must not send live orders"
                            ),
                        ):
                            ciclo_principal()

        balances = paper_state.obtener_balances_paper(0)
        self.assertGreater(balances["btc"], 0)
        self.assertEqual(paper_state.get_state("position")["crypto"], "btc")


if __name__ == "__main__":
    unittest.main()
