# Chat Seguro con Cifrado y Verificación de Integridad

Chat con **cuentas de usuario** (registro + inicio de sesión) que consume la
**CIA API** (`cia_api.py`) vía HTTP para cifrar y verificar la integridad de los
mensajes. Los mensajes se guardan en **PostgreSQL** y se leen desde ahí para
desplegarse en el chat.

## Requisitos cubiertos (miniProyecto.md)

- Cuentas de usuario: registro, inicio de sesión y sesión con token.
- Cada mensaje se **cifra** con `POST /confidentiality/encrypt`.
- Cada mensaje se **firma** con `POST /integrity/sign`.
- Se guarda en BD: cifrado + firma + remitente + timestamp.
- El chat **lee los mensajes desde la base de datos**.
- Se despliega con la leyenda **"No verificado"**.
- La app llama a `POST /integrity/verify`; si responde `valid: true`, la
  leyenda cambia a **"Mensaje verificado"**.
- El texto mostrado es el descifrado (`POST /confidentiality/decrypt`), nunca
  el cifrado.
- La CIA API se usa tal como fue proporcionada (solo se extendió para persistir
  las claves entre reinicios y habilitar CORS; no se quitó cifrado, firma ni
  verificación).

## Estructura

```
README.md                   Cómo ejecutar la aplicación (este archivo)
esquema.sql                 Modelo de la base de datos
cia_api.py                  CIA API (Confidencialidad, Integridad, Disponibilidad)
miniProyecto.md             Enunciado de la práctica
cia_api.md                  Ejemplos de uso de la CIA API
mensajeria_aes/
├── app.py                  Servidor del chat: API REST + WebSocket
├── auth.py                 Hash de contraseñas (PBKDF2) y tokens de sesión
├── cia_client.py           Cliente HTTP que consume la CIA API
├── db.py                   Conexión a PostgreSQL y consultas
├── static/index.html       Interfaz: registro, login y chat
├── requirements.txt        Dependencias de Python
├── start.sh                Arranca ambos servidores
└── MEMORIA.md              Memoria técnica del proyecto
```

> Las claves de cifrado (`.cia_keys/`) se generan solas al primer arranque y
> están excluidas del repositorio por seguridad.

## Requisitos previos

- Python 3.10+
- PostgreSQL corriendo con una base llamada `mensajeria`

```bash
# Crear la base (una sola vez)
sudo -u postgres psql -c "CREATE DATABASE mensajeria OWNER postgres;"

# Instalar dependencias
pip install -r mensajeria_aes/requirements.txt
```

## Cómo ejecutar

```bash
cd mensajeria_aes
./start.sh
```

Esto levanta:

| Servicio | Puerto | URL |
|---|---|---|
| CIA API | 8000 | http://127.0.0.1:8000/docs |
| Chat seguro | 8001 | http://127.0.0.1:8001 |

> Las tablas `users`, `sessions` y `messages` se crean automáticamente al
> primer arranque (modelo en `esquema.sql`).

## Flujo de funcionamiento

1. El usuario se **registra** (`POST /api/register`) e **inicia sesión**
   (`POST /api/login`), obteniendo un token de sesión.
2. El usuario escribe y envía un mensaje (REST o WebSocket, siempre con su token).
3. `app.py` llama a `/confidentiality/encrypt` y `/integrity/sign`.
4. El cifrado, su firma, remitente y timestamp se **guardan en la BD**.
5. La app consulta la BD y despliega el mensaje con **"No verificado"**.
6. La app descifra (`/confidentiality/decrypt`) para mostrar el texto plano.
7. La app llama a `/integrity/verify`; si `valid: true`, la leyenda cambia a
   **"Mensaje verificado"**.

## Endpoints

### Autenticación

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/register` | Crea una cuenta `{username, password}` |
| `POST` | `/api/login` | Inicia sesión y devuelve `{token, username}` |
| `POST` | `/api/logout` | Cierra la sesión (borra el token) |
| `GET` | `/api/me` | Valida el token y devuelve el usuario |

### Mensajes (requieren `Authorization: Bearer <token>`)

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/send` | Envía, cifra, firma, guarda y verifica un mensaje |
| `GET` | `/api/messages` | Lee los mensajes desde la BD |
| `POST` | `/api/messages/{id}/validate` | Revalida un mensaje con `/integrity/verify` |
| `GET` | `/api/messages/{id}/plaintext` | Texto descifrado vía `/confidentiality/decrypt` |
| `WS` | `/ws?token=...` | Chat en tiempo real (autenticado por token) |

## Demostración de manipulación (para el docente)

1. Iniciar sesión con una cuenta y enviar un mensaje; esperar a que diga
   **"Mensaje verificado"**.
2. Alterar el texto cifrado directamente en la base de datos:

```bash
sudo -u postgres psql -d mensajeria \
  -c "UPDATE messages SET ciphertext = 'TAMPERED' || substr(ciphertext, 9) WHERE id = 1;"
```

3. Llamar a `POST /api/messages/1/validate` (con token) → el estado queda
   **"Verificación fallida"**, demostrando que la integridad se detecta.
