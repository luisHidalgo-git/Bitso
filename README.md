# Escáner dinámico multi-mercado de Bitso

Bot de trading automatizado para Bitso que monitorea cada 30 minutos el rendimiento de criptomonedas contra pesos mexicanos (MXN) y, si detecta una tendencia alcista fuerte, simula una compra.

Por defecto, el script **no ejecuta órdenes reales**: la línea de compra está comentada como medida de seguridad.

## ⚠️ Advertencia

Este proyecto es educativo y experimental. **No es una estrategia probada ni garantiza rentabilidad.**

Comprar únicamente el activo con mayor subida en 24 horas puede implicar comprar después de un movimiento fuerte y enfrentar una corrección posterior. Además, el bot:

- Solo compra; no vende.
- No implementa stop-loss ni toma de ganancias.
- No considera comisiones, spread, liquidez ni slippage.
- Puede comprar el mismo activo repetidamente cada 30 minutos si se cumplen las condiciones.
- Usa órdenes de mercado, cuyo precio final puede diferir del precio observado durante el escaneo.

Úsalo primero en modo simulación y con fondos que puedas permitirte perder.

## 📌 ¿Qué hace?

1. Carga las credenciales de Bitso desde un archivo `.env`.
2. Consulta el saldo disponible en MXN de tu cuenta.
3. Consulta los tickers públicos de Bitso.
4. Filtra únicamente los mercados incluidos en la lista blanca y denominados en MXN.
5. Ordena los mercados por su variación porcentual de las últimas 24 horas (`change_24`).
6. Si el mejor mercado supera el umbral de ganancia y hay saldo suficiente, genera una orden de compra simulada.
7. Espera 30 minutos y repite el ciclo indefinidamente.

## ⚙️ Parámetros de estrategia

| Parámetro | Valor actual | Descripción |
|---|---:|---|
| `MONTO_OPERACION_MXN` | `200.0` | Monto máximo a gastar por operación, en MXN. |
| `SALDO_MINIMO_REQUERIDO` | `50.0` | Saldo mínimo en MXN necesario para operar. |
| `UMBRAL_MINIMO_GANANCIA` | `1.0` | Variación mínima de 24h para considerar una compra, en porcentaje. |
| `MONEDAS_PERMITIDAS` | BTC, ETH, XRP, SOL | Lista blanca de pares contra MXN que el bot puede analizar. |

Puedes modificar estos valores directamente en el script:

```python
MONTO_OPERACION_MXN = 200.0
SALDO_MINIMO_REQUERIDO = 50.0
UMBRAL_MINIMO_GANANCIA = 1.0

MONEDAS_PERMITIDAS = [
    "btc_mxn",
    "eth_mxn",
    "xrp_mxn",
    "sol_mxn"
]
```

## 🧰 Requisitos

- Python 3.7 o superior.
- Cuenta de Bitso.
- API Key y API Secret de Bitso.
- Permisos de API para consultar balance.
- Permisos de trading, únicamente si activas compras reales.
- Conexión a internet.

## 📦 Instalación

Clona el repositorio:

```bash
git clone [https://github.com/tu-usuario/tu-repositorio.git](https://github.com/tu-usuario/tu-repositorio.git)
cd tu-repositorio
```

Instala las dependencias:

```bash
pip install -r requirements.txt
```

## 🔐 Configuración

Crea un archivo llamado `.env` en la raíz del proyecto:

```env
BITSO_API_KEY=tu_api_key_de_bitso
BITSO_API_SECRET=tu_api_secret_de_bitso
```

**Nunca compartas ni subas tu archivo `.env` a GitHub.**

Agrega esta línea a tu archivo `.gitignore`:

```gitignore
.env
```

## ▶️ Ejecución

Guarda el script como `bitso_scanner.py` y ejecútalo:

```bash
python bitso_scanner.py
```

El bot iniciará un bucle continuo y mostrará información como:

- Saldo MXN disponible.
- Mercado con mejor desempeño dentro de la lista permitida.
- Precio actual y variación de 24 horas.
- Si cumple o no las condiciones para comprar.

Para detener el bot, presiona:

```bash
Ctrl + C
```

## 🧠 Lógica de decisión

El bot selecciona el mercado con mayor variación positiva en 24 horas entre los pares permitidos.

Si cumple estas condiciones:

```text
variacion_24h >= UMBRAL_MINIMO_GANANCIA
saldo_mxn >= SALDO_MINIMO_REQUERIDO
```

Entonces calcula:

```python
monto_a_gastar = min(MONTO_OPERACION_MXN, saldo_mxn_disponible)
```

Y muestra una compra simulada por ese monto.

## 🔏 Autenticación con Bitso

Para endpoints privados, el script genera un `nonce` basado en la hora actual y firma la petición con HMAC-SHA256 usando el API Secret.

La cabecera generada tiene este formato:

```text
Authorization: Bitso <API_KEY>:<nonce>:<firma>
```

La firma se calcula sobre:

```text
nonce + método HTTP + ruta + payload JSON
```

## 🛒 Compra real vs. simulación

Actualmente, la compra es simulada:

```python
# ejecutar_orden(
#     mejor_mercado["book"],
#     side="buy",
#     tipo_monto="minor",
#     valor=monto_a_gastar
# )

print(
    f"[Simulación] Se habrían comprado ${monto_a_gastar} MXN "
    f"de {mejor_mercado['book'].upper()}."
)
```

Si descomentas la llamada a `ejecutar_orden(...)`, el bot enviará una **orden de mercado real de compra** a Bitso.

Una orden de mercado se ejecuta al mejor precio disponible en ese momento, por lo que puede haber diferencias entre el precio mostrado durante el análisis y el precio final de ejecución.

## 🧪 Ejemplo de salida

```text
Iniciando escáner dinámico multi-mercado de Bitso...

--- Escaneando el mercado global de Bitso ---
💰 Saldo MXN disponible: $1,250.00
🏆 Mercado líder actual: SOL_MXN
   -> Precio: $2,041.78 | Variación 24h: +3.25%
🚀 ¡Tendencia alcista fuerte en SOL_MXN! Comprando con $200.0 MXN...
[Simulación] Se habrían comprado $200.0 MXN de SOL_MXN.

Esperando el próximo ciclo de escaneo (30 minutos)...
```

## 🚧 Posibles mejoras

- Agregar venta automática.
- Implementar stop-loss y objetivo de ganancia.
- Evitar comprar el mismo activo en ciclos consecutivos.
- Registrar operaciones en CSV o una base de datos.
- Validar volumen mínimo antes de operar.
- Manejar errores HTTP y reintentos de forma más robusta.
- Usar órdenes limit en lugar de órdenes market.
- Agregar pruebas unitarias y logs.

## 📄 Licencia

Puedes agregar la licencia que prefieras, por ejemplo MIT:

```text
MIT License
```