# Chat Seguro con Cifrado y Verificación de Integridad — Memoria Técnica y Guía para el Docente

Proyecto de **Seguridad Informática** para la práctica *"Chat Seguro con
Cifrado y Verificación de Integridad"* (`miniProyecto.md`): una aplicación de
mensajería entre **usuarios con cuentas propias** (registro y login) donde
cada mensaje se **cifra** y se **firma** usando la **CIA API**, se guarda en
una base de datos y se **verifica**, cambiando su estado de *"No verificado"* a
*"Mensaje verificado"*.

Este documento está escrito pensando en que quien lo lea está empezando en el
tema. Cada concepto se explica desde cero, con analogías, y después se explica
cómo quedó implementado en el código.

---

## 1. Índice

1. [Qué se entregó y cómo ejecutarlo](#2-qué-se-entregó-y-cómo-ejecutarlo)
2. [Conceptos y teoría](#3-conceptos-y-teoría)
3. [El problema que resuelve la práctica](#4-el-problema-que-resuelve-la-práctica)
4. [Arquitectura de la aplicación](#5-arquitectura-de-la-aplicación)
5. [Explicación archivo por archivo](#6-explicación-archivo-por-archivo)
6. [El flujo completo paso a paso](#7-el-flujo-completo-paso-a-paso)
7. [Endpoints de la API](#8-endpoints-de-la-api)
8. [La tabla de mensajes en PostgreSQL](#9-la-tabla-de-mensajes-en-postgresql)
9. [Cómo se cumplen los requisitos de la práctica](#10-cómo-se-cumplen-los-requisitos-de-la-práctica)
10. [Demo para el docente (guion)](#11-demo-para-el-docente-guion)
11. [Posibles preguntas del docente y sus respuestas](#12-posibles-preguntas-del-docente-y-sus-respuestas)

---

## 2. Qué se entregó y cómo ejecutarlo

### 2.1 Archivos del proyecto

| Archivo | Rol |
|---|---|
| `cia_api.py` | CIA API proporcionada (se extendió: claves persistentes + CORS) |
| `mensajeria_aes/app.py` | Servidor del chat: API REST + WebSocket + frontend |
| `mensajeria_aes/cia_client.py` | Cliente HTTP que consume la CIA API |
| `mensajeria_aes/db.py` | Conexión a PostgreSQL y consultas de la tabla `messages` |
| `mensajeria_aes/static/index.html` | Interfaz web: registro, login y chat |
| `esquema.sql` | Script/modelo de la base de datos (entregable) |
| `mensajeria_aes/start.sh` | Script que arranca ambos servidores |
| `mensajeria_aes/requirements.txt` | Librerías de Python necesarias |
| `README.md` (raíz) | README breve para ejecutar la app (entregable) |
| `MEMORIA.md` | Este documento |

### 2.2 Cómo ejecutarla

Requisitos: Python 3.10+, PostgreSQL corriendo y una base llamada `mensajeria`.

```bash
# 1) Instalar las librerías
pip install -r mensajeria_aes/requirements.txt

# 2) Crear la base de datos en PostgreSQL (una sola vez)
sudo -u postgres psql -c "CREATE DATABASE mensajeria OWNER postgres;"

# 3) Arrancar todo (CIA API + chat)
cd mensajeria_aes
./start.sh
```

Luego abrir en el navegador:

- **Chat**: `http://127.0.0.1:8001`
- **CIA API (Swagger)**: `http://127.0.0.1:8000/docs`

La tabla de mensajes se crea sola al primer arranque.

---

## 3. Conceptos y teoría

### 3.1 La Tríada CIA (Confidencialidad, Integridad, Disponibilidad)

Es el modelo base de la seguridad de la información. Todo sistema de seguridad
se evalúa con estos tres pilares, y la CIA API (`cia_api.py`) los demuestra con
tres grupos de endpoints:

| Pilar | ¿Qué significa? | Endpoints de la CIA API |
|---|---|---|
| **C** — Confidencialidad | Solo quien tiene permiso puede leer el mensaje | `/confidentiality/encrypt`, `/confidentiality/decrypt` |
| **I** — Integridad | El mensaje no fue alterado en el camino | `/integrity/sign`, `/integrity/verify` |
| **A** — Disponibilidad | El servicio responde cuando se necesita | `/availability/status`, `/availability/request` |

**La práctica usa los dos primeros:** la confidencialidad (cifrar con la CIA
API) y la integridad (firmar y verificar con la CIA API). La disponibilidad
está implícita en que el servicio corre y responde.

### 3.2 Cifrado simétrico (Fernet / AES)

- **Cifrar** = transformar un texto legible (texto plano) en algo ilegible
  (cifrado), de forma que **solo quien tiene la clave** pueda volverlo legible.
- **Simétrico** = se usa **la misma clave** para cifrar y para descifrar.
- La CIA API usa **Fernet**, una librería de `cryptography` que implementa
  **AES-128-CBC** combinado con **HMAC-SHA256**. Es cifrado autenticado: no
  solo oculta el texto, sino que cualquier manipulación del texto cifrado se
  detecta y la API responde `403`.
- La clave de la CIA API se genera al primer arranque y se guarda en
  `.cia_keys/fernet.key` (extensión agregada). En producción viviría en un
  gestor de secretos.

> **Analogía:** el cifrado es una caja fuerte con candado y llave. Solo quien
> tiene la llave puede abrirla. Si alguien forcejea la caja, el sello
> (HMAC) se rompe y lo notamos al abrir.

### 3.3 Firma HMAC-SHA256 (integridad)

- Una **firma** es un dato que se genera a partir del mensaje y una **clave
  secreta de firma** (en la CIA API: `.cia_keys/signing.key`).
- Es **unidireccional**: de la firma no se puede recuperar el mensaje.
- Tiene efecto **avalancha**: si cambias **una sola letra** del mensaje, la
  firma cambia por completo.
- Al **verificar**, se recalcula la firma esperada con la clave secreta y se
  compara con la firma guardada. Si coinciden → `valid: true` → el mensaje no
  fue alterado.

> **Analogía:** la firma es como una **huella digital** o un **lacre**: se
> calcula sobre el mensaje exacto. Si el mensaje cambia aunque sea un carácter,
> la huella ya no corresponde.

### 3.4 ¿Cifrado y firma son lo mismo?

| | Cifrar (Fernet/AES) | Firmar (HMAC-SHA256) |
|---|---|---|
| ¿Es reversible? | Sí, con la clave | No, es unidireccional |
| ¿Qué protege? | Confidencialidad (no se lee) | Integridad (no se altera) |
| ¿Salida? | Texto cifrado del tamaño del original | Cadena fija de 64 caracteres hex |
| Uso típico | Guardar mensajes privados | Detectar alteraciones |

**En esta práctica se usan los dos:**
1. El mensaje se **cifra** (`/confidentiality/encrypt`) para que en la base de
   datos nadie pueda leerlo.
2. Se le **firma** (`/integrity/sign`) para poder comprobar después que nadie
   lo modificó.

### 3.5 Validación de integridad (la idea central de la práctica)

La práctica pide exactamente este ciclo:

1. Cuando se envía el mensaje, se guarda en la BD con la leyenda **"No
   verificado"**.
2. En la misma tabla se guardan: **id**, **mensaje cifrado**, **firma**,
   **remitente** y **timestamp**.
3. Se **verifica**: se descifra el mensaje (`/confidentiality/decrypt`) y se
   llama a `/integrity/verify` con el texto plano y la firma guardada.
4. Si la respuesta es `valid: true` → el mensaje es íntegro → la leyenda
   cambia a **"Mensaje verificado"**.
5. Si no → el mensaje fue alterado → **"Verificación fallida"**.

Piénsalo como comparar la huella guardada en un registro contra la huella
sacada en el momento: si son iguales, la persona es la misma; si no, no.

### 3.6 API REST y consumo vía HTTP

- Una **API** (Interfaz de Programación de Aplicaciones) es una forma de que
  programas se hablen entre sí usando HTTP.
- **REST** es un estilo: cada "acción" es una dirección (URL) y un verbo HTTP.
  Los datos viajan en formato **JSON** (`{"clave": "valor"}`).
- En esta práctica, **el chat no cifra ni firma por su cuenta**: consume la CIA
  API vía HTTP. Por ejemplo, cifrar es un `POST` a `/confidentiality/encrypt`
  con `{"message": "hola"}` que responde `{"ciphertext": "..."}`.

### 3.7 WebSocket (tiempo real)

- HTTP normal funciona así: el cliente pide y el servidor responde. Punto. Para
  ver mensajes nuevos tendrías que volver a pedir (recargar).
- **WebSocket** abre una **conexión permanente** en dos direcciones: el servidor
  puede **empujar** datos al cliente sin que este lo pida. Por eso el chat se
  actualiza solo en ambas ventanas.

### 3.8 PostgreSQL (base de datos relacional)

- Una base de datos **relacional** guarda datos en **tablas** (como hojas de
  cálculo): filas y columnas.
- Nuestro proyecto tiene tres tablas: `users` (cuentas), `sessions` (sesiones)
  y `messages` (mensajes).
- La práctica exige que el chat **lea los mensajes desde la base de datos**,
  no que los mantenga en memoria. Eso se cumple: cada pantalla consulta la
  tabla `messages`.

### 3.9 Cuentas de usuario y sesiones (autenticación)

Para que cada usuario tenga su propia cuenta:

- **Tabla `users`**: guarda `username` y **nunca la contraseña en texto
  plano**; guarda su **hash PBKDF2-SHA256** con un *salt* aleatorio.
- **Hash de contraseña (PBKDF2)**: una función que convierte la contraseña en
  una huella irreversible. Al iniciar sesión se recalcula y compara. Si la BD
  se filtra, el atacante no puede leer las contraseñas.
- **Token de sesión**: al iniciar sesión el servidor genera un token aleatorio,
  lo guarda en la tabla `sessions` y se lo entrega al navegador. El navegador
  lo manda en cada petición (`Authorization: Bearer <token>`) y en el WebSocket
  (`/ws?token=...`) para que el servidor sepa quién es.
- **El remitente nunca lo dice el cliente**: el servidor lo obtiene del token.
  Así nadie puede hacerse pasar por otro usuario.

> **Analogía del token:** el token es como una **pulsera de acceso** que te dan
> en la entrada. La llevas puesta toda la visita; en cada puerta la muestras y
> el personal sabe quién eres sin preguntarte el nombre otra vez.

---

## 4. El problema que resuelve la práctica

En un chat normal, el mensaje se guarda **tal cual**: cualquiera con acceso a
la base de datos podría leerlo o modificarlo sin dejar rastro.

La práctica pide demostrar que podemos:
1. **Ocultar** el contenido → cifrado con `/confidentiality/encrypt`.
2. **Detectar** cualquier alteración → firma con `/integrity/sign` y
   verificación con `/integrity/verify`.

La leyenda de cada mensaje (**"No verificado"** → **"Mensaje verificado"** /
**"Verificación fallida"**) **es la evidencia visible** de que la verificación
de integridad está ocurriendo.

---

## 5. Arquitectura de la aplicación

```
        ┌────────────────────────────────────────────┐
        │              Navegador                     │
        │  Pantalla de login / registro  ─┐          │
        │  Chat con mi sesión (token)     ─┤         │
        │  (una pestaña por usuario)       │         │
        └──────────────────────┬──────────┼──────────┘
                               │ WebSocket │ HTTP (token)
                               ▼           ▼
        ┌────────────────────────────────────────────┐
        │        Chat seguro — app.py (puerto 8001)  │
        │   auth.py (PBKDF2 + tokens)                │
        │   cia_client.py  ──HTTP──►  CIA API 8000   │
        │       │ encrypt · sign · decrypt · verify  │
        │       ▼                                    │
        │   db.py ──► PostgreSQL (users/sessions/    │
        │               messages)                    │
        └────────────────────────────────────────────┘
```

**Tecnologías usadas:**

| Tecnología | Para qué se usa |
|---|---|
| Python 3 | Lenguaje de programación de todo el backend |
| FastAPI | Framework web de la CIA API y del chat |
| uvicorn | Servidor que ejecuta las aplicaciones FastAPI |
| cryptography (Fernet) | Cifrado AES + HMAC dentro de la CIA API |
| httpx | Cliente HTTP con el que el chat consume la CIA API |
| psycopg | Driver de Python para hablar con PostgreSQL |
| PostgreSQL | Base de datos relacional |
| HTML / CSS / JavaScript | Interfaz visual del chat |

---

## 6. Explicación archivo por archivo

### 6.1 `cia_api.py` — la CIA API proporcionada

Es la API de la práctica. Proporciona cifrado, firma, verificación y
disponibilidad. **Se usó tal como fue proporcionada**, con dos extensiones que
no quitan ninguna funcionalidad:

1. **Persistencia de claves** (`.cia_keys/fernet.key` y `.cia_keys/signing.key`):
   antes las claves se regeneraban en cada arranque y los mensajes cifrados
   perdían valor al reiniciar. Ahora sobreviven reinicios.
2. **CORS habilitado**: permite que el navegador (o cualquier cliente) consuma
   la API vía HTTP.

### 6.2 `cia_client.py` — el puente HTTP hacia la CIA API

Es el corazón de la práctica: **todo cifrado, firma, descifrado y verificación
se hace llamando a la CIA API por HTTP**, no en el chat.

```python
async def encrypt(message):   # -> POST /confidentiality/encrypt
async def decrypt(ciphertext):  # -> POST /confidentiality/decrypt
async def sign(message):      # -> POST /integrity/sign
async def verify(message, signature):  # -> POST /integrity/verify
```

### 6.3 `auth.py` — autenticación

- `hash_password()` → genera el hash **PBKDF2-SHA256** con *salt* aleatorio.
- `verify_password()` → compara la contraseña contra el hash guardado.
- `generate_token()` → crea un token de sesión aleatorio (la "pulsera de
  acceso" del usuario).

### 6.4 `db.py` — la base de datos

- Define la **DSN** (dirección de la base de datos):
  `postgresql://postgres:postgres@localhost:5432/mensajeria`
- `SCHEMA` crea las tablas `users`, `sessions` y `messages` si no existen.
- `create_user()` / `get_user_by_username()` → **REGISTRO y LOGIN**.
- `create_session()` / `get_user_by_token()` / `delete_session()` → manejo de
  **tokens de sesión**.
- `create_message(sender, ciphertext, firma)` → **GUARDADO EN BD**: inserta
  cifrado, firma, remitente y timestamp.
- `list_messages()` / `get_message(id)` → **LECTURA DESDE BD** para desplegar.
- `update_status(id, status)` → cambia la leyenda tras la verificación.

### 6.5 `app.py` — el servidor del chat

Define los **endpoints** (registro, login, logout, mensajes) y el **WebSocket**
(ver sección 7). Orquesta el flujo completo llamando a `auth`, `cia_client`
(cifrar → firmar → guardar → descifrar → verificar) y a `db`. El código está
comentado señalando dónde se cifra, firma, guarda y verifica.

### 6.6 `static/index.html` — el chat

- Pantalla de **registro / inicio de sesión**.
- Tras entrar, muestra el **chat** con el usuario en la barra superior; el token
  se guarda en el navegador (`localStorage`) y se manda en cada petición y en
  el WebSocket (`/ws?token=...`).
- Cada burbuja de mensaje muestra el **remitente**, su **id** y una **etiqueta
  de estado**:
  - gris = **"No verificado"**, verde = **"Mensaje verificado"**, rojo =
    **"Verificación fallida"**.
- Al recibir `new_message`, muestra la burbuja; al recibir `status_update`,
  cambia la etiqueta sin recargar la página.
- El texto mostrado siempre es el **descifrado** que envía el servidor (que lo
  obtuvo de `/confidentiality/decrypt`), nunca el cifrado.

### 6.7 `esquema.sql` — modelo de la base de datos (entregable)

Script SQL con la definición de las tablas `users`, `sessions` y `messages`.
Se puede ejecutar manualmente o dejarlo que la app las cree solas.

### 6.8 `start.sh` — arranque

Mata instancias previas y levanta **ambos** servidores en segundo plano:
CIA API (puerto 8000) y chat (puerto 8001). Un solo comando para la demo.

---

## 7. El flujo completo paso a paso

Esto es lo que ocurre cuando un usuario con sesión iniciada escribe *"Hola"* y
pulsa Enviar:

1. **El navegador** envía `"Hola"` por el WebSocket, junto con el token de
   sesión (`/ws?token=...`).
2. **`app.py`** valida el token en la tabla `sessions` y obtiene el remitente.
3. **`app.py`** llama a `cia_client.encrypt("Hola")`, que hace
   `POST /confidentiality/encrypt` → recibe el **ciphertext**.
4. **`app.py`** llama a `cia_client.sign("Hola")`, que hace
   `POST /integrity/sign` → recibe la **firma** HMAC.
5. **`db.py`** inserta en PostgreSQL la fila:
   `(id, remitente, ciphertext, firma, "No verificado", timestamp)`.
6. **`app.py`** llama a `cia_client.decrypt(ciphertext)` (es decir, a
   `/confidentiality/decrypt`) para obtener el texto que se mostrará, y
   transmite por WebSocket a las ventanas el mensaje con la leyenda
   **"No verificado"**.
7. A los 1.2 segundos (simulación del paso de verificación), **`app.py`**
   descifra de nuevo y llama a `cia_client.verify(texto, firma)` (es decir,
   `POST /integrity/verify`).
8. Como responde `valid: true` → `db.update_status(id, "Mensaje verificado")`
   y por WebSocket se notifica el cambio → las ventanas de los usuarios
   conectados cambian la etiqueta a **verde**.

**Si un atacante modificara el ciphertext en la base de datos** (paso 4 bis),
al intentar descifrar la CIA API respondería `403`, o bien la verificación
respondería `valid: false` → la leyenda quedaría en **"Verificación fallida"**.

---

## 8. Endpoints de la API

### 8.1 Chat (puerto 8001)

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/api/register` | Registra una cuenta `{username, password}` |
| `POST` | `/api/login` | Inicia sesión y devuelve `{token, username}` |
| `POST` | `/api/logout` | Cierra la sesión (borra el token) |
| `GET` | `/api/me` | Valida el token y devuelve el usuario |
| `POST` | `/api/send` | Envía, cifra, firma, guarda y verifica un mensaje (requiere token) |
| `GET` | `/api/messages` | Lee los mensajes desde la BD |
| `GET` | `/api/messages/{id}` | Trae un mensaje por su id |
| `POST` | `/api/messages/{id}/validate` | Revalida con `/integrity/verify` y actualiza la leyenda |
| `GET` | `/api/messages/{id}/plaintext` | Texto descifrado vía `/confidentiality/decrypt` |
| `WS` | `/ws?token=...` | Chat en tiempo real (autenticado por token) |

Los endpoints de mensajes exigen el header `Authorization: Bearer <token>`.
El WebSocket exige el token como parámetro de la URL.

### 8.2 CIA API (puerto 8000, proporcionada)

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/confidentiality/encrypt` | Cifra un mensaje |
| `POST` | `/confidentiality/decrypt` | Descifra un mensaje (403 si es inválido) |
| `POST` | `/integrity/sign` | Genera la firma HMAC de un mensaje |
| `POST` | `/integrity/verify` | Verifica un (mensaje, firma); `valid: true/false` |
| `GET` | `/availability/status` | Estado de los nodos redundantes |
| `GET` | `/availability/request` | Petición con failover automático |

---

## 9. Las tablas en PostgreSQL

```sql
CREATE TABLE users (          -- cuentas de usuario
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,        -- hash PBKDF2 (nunca texto plano)
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE sessions (       -- sesiones activas (tokens)
    token      TEXT PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (       -- mensajes del chat
    id          BIGSERIAL PRIMARY KEY,   -- identificador único (autoincrementa)
    sender      TEXT NOT NULL,           -- remitente (el usuario de la sesión)
    ciphertext  TEXT NOT NULL,           -- mensaje cifrado con la CIA API
    firma       TEXT NOT NULL,           -- firma HMAC generada por /integrity/sign
    status      TEXT NOT NULL DEFAULT 'No verificado',  -- la leyenda de la práctica
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()      -- timestamp
);
```

El campo `status` es el protagonista de la práctica: comienza en
**"No verificado"** y cambia a **"Mensaje verificado"** cuando
`/integrity/verify` responde `valid: true`, o a **"Verificación fallida"**
cuando no.

---

## 10. Cómo se cumplen los requisitos de la práctica

| Requisito | Dónde se cumple |
|---|---|
| Cuentas de usuario y login | Tabla `users` + `POST /api/register`, `/api/login` |
| Sesión con token | Tabla `sessions` + header `Authorization: Bearer` + `/ws?token=` |
| Contraseñas protegidas | `auth.py` con hash PBKDF2-SHA256 (nunca texto plano) |
| Cifrar con `POST /confidentiality/encrypt` | `app.py` → `cia_client.encrypt()` |
| Firmar con `POST /integrity/sign` | `app.py` → `cia_client.sign()` |
| Guardar cifrado + firma + remitente + timestamp | `db.create_message()` inserta esas 4 columnas |
| Leer los mensajes desde la BD | `GET /api/messages` → `db.list_messages()` |
| Leyenda **"No verificado"** al desplegar | `status` default y burbujas del chat |
| Llamar a `POST /integrity/verify` y si `valid: true` cambiar a **"Mensaje verificado"** | `validate_and_notify()` y `POST /api/messages/{id}/validate` |
| Mostrar texto descifrado (`/confidentiality/decrypt`), nunca el cifrado | `app.py` descifra vía API antes de enviar al navegador |
| Usar la CIA API tal como fue proporcionada | Solo se extendió (persistencia de claves + CORS), sin quitar nada |
| Código comentado marcando cifra/firma/guarda/verifica | Comentarios `PASO 2a`, `PASO 2b`, `PASO 3`, `PASO 5`, `PASO 6` en `app.py` y docstrings |
| Entregables: script de BD y README | `esquema.sql` y `README.md` |

---

## 11. Demo para el docente (guion)

1. **Arrancar**: `./start.sh`
2. **Abrir** `http://127.0.0.1:8001` → aparece la pantalla de **registro/login**.
3. **Registrar** la cuenta "alice" y entrar. Abrir la página en una **segunda
   pestaña/ventana** y registrar/entrar con "bob".
4. Enviar mensajes de alice a bob: cada burbuja aparece con la etiqueta **gris
   "No verificado"** y, ~1.2s después, cambia a **verde "Mensaje verificado"**
   en ambas ventanas.
5. **Mostrar que las contraseñas no se guardan en texto plano**:
   ```bash
   sudo -u postgres psql -d mensajeria -c "SELECT username, left(password_hash,25) FROM users;"
   ```
   Se ve solo el hash PBKDF2.
6. **Mostrar el cifrado y la firma en la BD**:
   ```bash
   sudo -u postgres psql -d mensajeria -c "SELECT id, sender, left(ciphertext,20) AS cifrado, left(firma,12) AS firma, status FROM messages;"
   ```
   El campo `ciphertext` es ilegible y la `firma` está guardada.
7. **Demostrar la manipulación (lo más impactante)**: alterar un mensaje
   directamente en la base de datos:
   ```bash
   sudo -u postgres psql -d mensajeria -c "UPDATE messages SET ciphertext = 'TAMPERED' || substr(ciphertext, 9) WHERE id = 1;"
   ```
   Luego `POST /api/messages/1/validate` (con token) → la leyenda queda
   **"Verificación fallida"**. El sistema detecta que el mensaje fue alterado.
8. **Mostrar que el chat solo consume la CIA API por HTTP**: en el Swagger de
   la CIA API (`http://127.0.0.1:8000/docs`) se ven los endpoints que el chat
   invoca (`/confidentiality/encrypt`, `/integrity/sign`, `/integrity/verify`,
   `/confidentiality/decrypt`).

---

## 12. Posibles preguntas del docente y sus respuestas

**¿Por qué el chat no cifra directamente?**
La práctica exige consumir la CIA API vía HTTP. Por eso el chat es un cliente
de la API: para cifrar llama a `POST /confidentiality/encrypt`, para firmar a
`POST /integrity/sign`, para verificar a `POST /integrity/verify` y para
mostrar el texto a `POST /confidentiality/decrypt`. Nunca usa las claves
directamente.

**¿Cómo se guardan las contraseñas?**
Nunca en texto plano: se guarda el hash PBKDF2-SHA256 con salt aleatorio
(`auth.py`). Si la base de datos se filtra, las contraseñas siguen siendo
ilegibles.

**¿Cómo sabe el servidor quién envía cada mensaje?**
Por el **token de sesión**. Al iniciar sesión el servidor entrega un token
aleatorio guardado en la tabla `sessions`; el navegador lo manda en cada
petición (`Authorization: Bearer`) y en el WebSocket (`/ws?token=`), y el
servidor resuelve a qué usuario pertenece. El remitente nunca se toma del texto
que manda el cliente.

**¿Qué diferencia hay entre cifrar y firmar?**
Cifrar es reversible con la clave (protege la confidencialidad). Firmar es
unidireccional y sirve para detectar cambios (integridad). La práctica usa
ambos: Fernet para ocultar y HMAC-SHA256 para validar.

**¿Qué pasa si se modifica el ciphertext en la base de datos?**
Dos protecciones actúan: la CIA API detecta que el ciphertext fue alterado
(HMAC del Fernet, responde 403 al descifrar) y, si se intentara verificar, la
firma ya no coincide → `valid: false` → leyenda **"Verificación fallida"**.

**¿Por qué el estado empieza "No verificado"?**
Porque es la demostración del proceso: primero se guarda y se despliega, y
después se verifica con `/integrity/verify`. El cambio visible de etiqueta es
la prueba de que la verificación ocurre.

**¿Dónde se guardan las claves de la CIA API?**
En `.cia_keys/` (se generan al primer arranque y se reutilizan). En un sistema
real irían en un gestor de secretos. Se explicó en el código.

**¿Cómo funciona el tiempo real?**
Con WebSocket: una conexión permanente bidireccional. El servidor transmite el
mensaje nuevo y el cambio de estado a las dos ventanas sin recargar. La
verificación de integridad se hace siempre en el servidor.

**¿Qué es lo que se extendió de la CIA API?**
Persistencia de claves (para que los mensajes sobrevivan reinicios) y CORS
(para permitir el consumo desde el navegador). No se quitó ni modificó el
cifrado, la firma ni la verificación originales.

---

*Documento generado como memoria técnica del proyecto. Código en
`mensajeria_aes/`.*
