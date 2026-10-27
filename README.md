# Bot de trading automático para Bitso

Bot de Python que consulta balances y mercados de Bitso, evalúa una estrategia
para pares contra MXN y reporta las decisiones en la consola y, opcionalmente,
por Telegram.

El bot tiene tres modos de operación: simulación (`paper`), operaciones reales
limitadas (`safe`) y el modo anterior de operaciones reales con todo el saldo
disponible (`full`). Por seguridad, si no se define un modo, se usa `paper`.

## Advertencia

Este proyecto es educativo y experimental. No es asesoría financiera, no es
una estrategia probada y no garantiza rentabilidad. Incluso el modo `safe`
puede perder dinero: el límite de tamaño no es una garantía de pérdida máxima,
y las órdenes de mercado están expuestas a volatilidad, comisiones, spread,
liquidez y slippage. En los modos reales, las reglas de salida venden todo el
saldo de la posición reconocida; esto también puede incluir criptomonedas
compradas fuera del bot. Revisa los permisos de la API y comienza en `paper`.

## Cómo funciona

Al iniciar, el bot carga las variables de entorno y envía un mensaje de inicio.
Después, `main.py` repite el ciclo de evaluación cada **60 segundos**. Los
balances y las órdenes se manejan según `MODO_OPERACION`:

- **`paper` (predeterminado):** usa un portafolio de simulación persistido en
  SQLite; no consulta balances privados ni envía órdenes a Bitso.
- **`safe`:** opera con dinero real, pero limita cada compra inicial o
  reinversión al menor valor entre el saldo MXN disponible, el 10 % del valor
  total estimado de la cuenta y el tamaño máximo calculado con el riesgo
  configurado. También exige tendencia positiva de BTC y ETH y volumen mínimo.
- **`full`:** conserva el comportamiento anterior: compra y reinvierte todo el
  saldo MXN disponible. Las ventas de salida liquidan la posición detectada.

En todos los modos, el bot:

1. Obtiene los balances: virtuales en `paper` y de la cuenta de Bitso en los
   modos reales.
2. Consulta los tickers públicos y filtra los pares permitidos contra MXN:
   BTC, ETH, XRP y SOL.
3. Ordena esos mercados por su variación de 24 horas y toma el de mayor
   variación como líder.
4. Si detecta una posición existente en alguna de esas criptomonedas, aplica
   estas reglas:
   - **Protección:** envía una orden de venta si el precio cae al menos 1.5 %
     desde el máximo registrado en el proceso, o si la variación de 24 horas
     del activo es negativa.
   - **Rotación:** si otro mercado es líder y su variación supera la del activo
     actual por al menos 2.5 puntos porcentuales, vende la posición y compra el
     líder con el saldo MXN disponible si alcanza el mínimo requerido.
   - Si no se activa ninguna regla, informa que mantiene la posición.
5. Si no detecta una posición, considera comprar el líder cuando se cumplen
   las reglas del modo y hay al menos 50 MXN para operar.
6. Espera un minuto y comienza el siguiente ciclo.

La posición se infiere de los balances. En `safe` y `paper`, la posición
gestionada y el máximo del trailing stop se guardan en SQLite; en `full`, el
máximo se conserva solo en memoria y se reinicia al cerrar el programa. Los
umbrales para reconocer balances como posiciones son BTC `0.0001`, ETH
`0.001`, XRP `1.0` y SOL `0.01`; una posición pequeña comprada y registrada por
el bot también se reconoce en `safe` y `paper`.

## Estructura del proyecto

```text
.
├── main.py                 # Punto de entrada y bucle de ejecución
├── railway.json            # Comando de inicio y política de reinicio en Railway
└── bitso_bot/
    ├── __init__.py
    ├── config.py           # Variables de entorno y parámetros
    ├── notifications.py    # Salida en consola y alertas de Telegram
    ├── bitso_api.py        # Firma, consultas y envío de órdenes a Bitso
    └── strategy.py         # Evaluación de balances y estrategia
```

`main.py` importa y ejecuta los componentes del paquete `bitso_bot`. Ejecuta el
bot desde la raíz del proyecto para que Python encuentre el paquete.

## Requisitos e instalación

- Python instalado.
- Cuenta y credenciales API de Bitso con permisos adecuados si usarás un modo
  real (`safe` o `full`).
- Conexión a internet.

Instala las dependencias desde la raíz del proyecto:

```bash
python -m pip install -r requirements.txt
```

## Configuración

Crea un archivo `.env` en la raíz del proyecto. Empieza con el modo seguro de
simulación:

```env
MODO_OPERACION=paper
CAPITAL_INICIAL_PAPER=1000
BITSO_API_KEY=tu_api_key_de_bitso
BITSO_API_SECRET=tu_api_secret_de_bitso
```

`CAPITAL_INICIAL_PAPER` establece el saldo MXN virtual inicial. Para activar
órdenes reales limitadas, cambia a `MODO_OPERACION=safe`; para recuperar el
comportamiento de todo el saldo, usa `MODO_OPERACION=full`. Los modos `safe` y
`full` requieren credenciales de Bitso. Usa una API con los permisos mínimos
necesarios; las credenciales no son necesarias en `paper`.

Para recibir notificaciones por Telegram, agrega también:

```env
TELEGRAM_BOT_TOKEN=token_de_tu_bot
TELEGRAM_CHAT_ID=id_del_chat
```

Telegram es opcional: si no se configuran ambas variables, los mensajes se
imprimen en la consola. No compartas ni subas `.env` al repositorio.
El estado SQLite de `paper` y `safe` se guarda en `data/` (o en la ruta
indicada por `RUTA_ESTADO`). Se conserva mientras el almacenamiento local del
despliegue sea persistente; en Railway, monta un volumen si necesitas mantener
ese archivo al reemplazar o recrear el contenedor.

## Ejecución

Desde la raíz del proyecto:

```bash
python main.py
```

Para detener el bucle, presiona `Ctrl + C`.

## Despliegue en Railway

Este proyecto se ejecuta como un **servicio worker**, no como una aplicación
web: no expone un puerto HTTP ni necesita un dominio público. Railway detecta
`requirements.txt` para instalar las dependencias y usa `railway.json` para
iniciar el proceso con `python main.py` y reiniciarlo si termina con error.

1. Sube el proyecto a un repositorio Git y crea un proyecto en Railway desde
   ese repositorio.
2. En el servicio, abre **Variables** y agrega:
   - `MODO_OPERACION=paper` para simulación (predeterminado).
   - `MODO_OPERACION=safe` para operaciones reales con límites.
   - `MODO_OPERACION=full` para operaciones reales con todo el saldo.
   - `BITSO_API_KEY` y `BITSO_API_SECRET` solo para los modos reales.
   - Opcionalmente `CAPITAL_INICIAL_PAPER` para el saldo virtual inicial.
   - Opcionalmente, `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`
3. Despliega el servicio y revisa **Deployments > View Logs** para confirmar
   que el bot inició correctamente.

No configures un dominio ni una variable `PORT`. Las variables de Railway
reemplazan el archivo `.env` local; no subas ese archivo al repositorio.

## Parámetros actuales

Los valores se definen en `bitso_bot/config.py`:

| Parámetro | Valor | Uso |
|---|---:|---|
| `SALDO_MINIMO_REQUERIDO` | `50.0` MXN | Saldo mínimo para una compra. |
| `UMBRAL_MINIMO_GANANCIA` | `2.0` % | Variación mínima de 24 horas para considerar la compra inicial. |
| `UMBRAL_DIFERENCIA_ROTACION` | `3.5` puntos porcentuales | Ventaja mínima de un líder apto para activar una rotación. |
| `PORCENTAJE_TRAILING_STOP` | `5.0` % | Caída desde el máximo que activa la venta al revisar el ciclo. |
| `MAX_EXPOSICION_PORCENTAJE` | `5.0` % | Exposición máxima de una compra en modo `safe` y `paper`. |
| `RIESGO_MAXIMO_OPERACION_PORCENTAJE` | `0.5` % | Riesgo estimado máximo por operación para calcular el tamaño. |
| `STOP_LOSS_ESTIMADO_PORCENTAJE` | `4.0` % | Caída desde la entrada que activa la venta al revisar el ciclo y supuesto para dimensionar el riesgo. |
| `VOLUMEN_MINIMO_MXN` | `50,000` MXN | Volumen mínimo estimado para comprar en `safe` y `paper`. |
| `COMISION_ESTIMADA_RATE` | `0.005` | Comisión usada en la simulación (`0.5 %`). |
| `MONEDAS_PERMITIDAS` | BTC, ETH, XRP y SOL contra MXN | Mercados que se analizan. |

En modo `safe`, el tamaño de compra es `min(saldo disponible, exposición
máxima, límite de riesgo)`. Con los valores predeterminados, la exposición por
operación es como máximo el 5 % del valor estimado de la cuenta. La estrategia
monitorea un stop de 4 % desde la entrada y un trailing stop de 5 % desde el
máximo, y exige una señal de entrada de 2 % y una ventaja de 3.5 puntos para
rotar. Estas reglas se evalúan cada minuto y ejecutan órdenes de mercado: no
son órdenes stop alojadas en Bitso ni límites garantizados de pérdida. El
slippage, las comisiones y movimientos rápidos pueden aumentar la pérdida.
En modo `full`, se conserva el comportamiento anterior y se usa todo el saldo
MXN disponible.

## API de Bitso y órdenes reales

Para consultar el balance, `bitso_bot/bitso_api.py` crea una firma HMAC-SHA256.
La firma se calcula a partir de:

```text
nonce + método HTTP + ruta + payload JSON
```

En los modos reales, la estrategia llama a `ejecutar_orden(...)` para enviar
órdenes de mercado a Bitso. Una respuesta exitosa de la API se reporta como
orden aceptada por Bitso, no como garantía de precio ni de ejecución final. Las
órdenes de mercado pueden ejecutarse a un precio distinto del observado
durante el análisis. En `paper`, las operaciones se registran localmente y no
se llama a la API privada.

## Limitaciones

- El precio de entrada y el máximo del trailing stop se guardan en `paper` y
  `safe`; en `full`, el estado solo permanece en memoria.
- La posición se determina a partir de los balances, no de un registro de
  operaciones del bot.
- La estrategia no calcula comisiones, spread, slippage ni rendimiento neto.
- Las consultas HTTP no configuran una política de reintentos.
