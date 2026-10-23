# Bot de monitoreo y simulación para Bitso

Bot de Python que consulta balances y mercados de Bitso, evalúa una estrategia
para pares contra MXN y reporta las decisiones en la consola y, opcionalmente,
por Telegram.

**El comportamiento actual es de simulación:** las llamadas que enviarían
órdenes de compra y venta reales están comentadas. Las alertas y mensajes de
simulación no ejecutan operaciones.

## Advertencia

Este proyecto es educativo y experimental. No es asesoría financiera, no es
una estrategia probada y no garantiza rentabilidad. La estrategia puede
reaccionar a movimientos pasados y no considera comisiones, spread, liquidez ni
slippage. Si se habilitan las llamadas de órdenes reales, estas pueden exponer
los fondos a pérdidas.

## Cómo funciona

Al iniciar, el bot carga las variables de entorno y envía un mensaje de inicio.
Después, `main.py` repite el ciclo de evaluación cada **60 segundos**:

1. Consulta los balances disponibles de la cuenta de Bitso.
2. Consulta los tickers públicos y filtra los pares permitidos contra MXN:
   BTC, ETH, XRP y SOL.
3. Ordena esos mercados por su variación de 24 horas y toma el de mayor
   variación como líder.
4. Si detecta una posición existente en alguna de esas criptomonedas, aplica
   estas reglas:
   - **Protección:** simula una venta si el precio cae al menos 1.5 % desde el
     máximo registrado en el proceso, o si la variación de 24 horas del activo
     es negativa.
   - **Rotación:** si otro mercado es líder y su variación supera la del activo
     actual por al menos 2.5 puntos porcentuales, reporta una rotación simulada.
   - Si no se activa ninguna regla, informa que mantiene la posición.
5. Si no detecta una posición, simula una compra del líder cuando su variación
   de 24 horas es al menos 1 % y hay por lo menos 50 MXN disponibles. El monto
   mostrado es el saldo MXN completo.
6. Espera un minuto y comienza el siguiente ciclo.

La posición se infiere de los balances de la cuenta; el máximo del trailing
stop se conserva solo en memoria y se reinicia al cerrar el programa. Los
umbrales usados para reconocer balances como posiciones son BTC `0.0001`, ETH
`0.001`, XRP `1.0` y SOL `0.01`.

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
- Cuenta de Bitso y credenciales API con permiso para consultar balances.
- Conexión a internet.

Instala las dependencias desde la raíz del proyecto:

```bash
python -m pip install -r requirements.txt
```

## Configuración

Crea un archivo `.env` en la raíz del proyecto:

```env
BITSO_API_KEY=tu_api_key_de_bitso
BITSO_API_SECRET=tu_api_secret_de_bitso
```

Las credenciales de Bitso son obligatorias porque el bot consulta los balances
privados. Para recibir notificaciones por Telegram, agrega también:

```env
TELEGRAM_BOT_TOKEN=token_de_tu_bot
TELEGRAM_CHAT_ID=id_del_chat
```

Telegram es opcional: si no se configuran ambas variables, los mensajes se
imprimen en la consola. No compartas ni subas `.env` al repositorio.

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
   - `BITSO_API_KEY`
   - `BITSO_API_SECRET`
   - Opcionalmente, `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`
3. Despliega el servicio y revisa **Deployments > View Logs** para confirmar
   que el bot inició correctamente.

No configures un dominio ni una variable `PORT`. Las variables de Railway
reemplazan el archivo `.env` local; no subas ese archivo al repositorio.

## Parámetros actuales

Los valores se definen en `bitso_bot/config.py`:

| Parámetro | Valor | Uso |
|---|---:|---|
| `SALDO_MINIMO_REQUERIDO` | `50.0` MXN | Saldo mínimo para la compra simulada inicial. |
| `UMBRAL_MINIMO_GANANCIA` | `1.0` % | Variación mínima de 24 horas para considerar esa compra. |
| `UMBRAL_DIFERENCIA_ROTACION` | `2.5` puntos porcentuales | Ventaja mínima del nuevo líder para simular una rotación. |
| `PORCENTAJE_TRAILING_STOP` | `1.5` % | Caída desde el máximo que activa la protección simulada. |
| `MONEDAS_PERMITIDAS` | BTC, ETH, XRP y SOL contra MXN | Mercados que se analizan. |

El script no limita el importe de la compra simulada a un monto fijo: muestra el
saldo MXN disponible completo.

## API de Bitso y órdenes reales

Para consultar el balance, `bitso_bot/bitso_api.py` crea una firma HMAC-SHA256.
La firma se calcula a partir de:

```text
nonce + método HTTP + ruta + payload JSON
```

El código incluye `ejecutar_orden(...)` para enviar órdenes de mercado, pero
las llamadas desde la estrategia están comentadas. En su estado actual, tanto
las compras como las ventas y rotaciones son únicamente simulaciones.

No habilites órdenes reales sin revisar cuidadosamente los importes, permisos y
riesgos. Si se descomentan llamadas, el bot puede enviar órdenes reales a
Bitso; las órdenes de mercado pueden ejecutarse a un precio distinto del
observado durante el análisis.

## Limitaciones

- El precio máximo del trailing stop no se guarda entre ejecuciones.
- La posición se determina a partir de los balances, no de un registro de
  operaciones del bot.
- La estrategia no calcula comisiones, spread, slippage ni rendimiento neto.
- Las consultas HTTP no configuran una política de reintentos.
