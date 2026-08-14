"""App de chat seguro con cuentas de usuario que consume la CIA API vía HTTP.

Cada usuario se registra y entra con su cuenta. El remitente de cada mensaje
se obtiene de la sesión (token), nunca del cliente.

Flujo esperado (miniProyecto.md):
  1. El usuario inicia sesión y escribe un mensaje.
  2. La app llama a /confidentiality/encrypt y /integrity/sign.
  3. El mensaje cifrado, su firma, remitente y timestamp se guardan en la BD.
  4. La app consulta la BD y despliega el mensaje con la leyenda "No verificado".
  5. La app descifra (/confidentiality/decrypt) para mostrar el texto plano.
  6. La app llama a /integrity/verify; si valid: true, la leyenda cambia a
     "Mensaje verificado".

Ejecutar (se requieren ambos servidores; ver start.sh):
    uvicorn cia_api:app --port 8000
    uvicorn app:app --port 8001
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import auth
import cia_client
import db

NO_VERIFICADO = "No verificado"
MENSAJE_VERIFICADO = "Mensaje verificado"
VERIFICACION_FALLIDA = "Verificación fallida"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    await cia_client.start_client()
    yield
    await cia_client.stop_client()
    await db.pool.close()


app = FastAPI(
    title="Chat Seguro con Cifrado y Verificación de Integridad",
    description=(
        "Chat User1 <-> User2 que consume la CIA API vía HTTP: cifra con "
        "/confidentiality/encrypt, firma con /integrity/sign, guarda en "
        "PostgreSQL y verifica con /integrity/verify."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Modelos
# ---------------------------------------------------------------------------
class SendRequest(BaseModel):
    message: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
def _token_from_header(authorization: str | None) -> str | None:
    """Extrae el token del header 'Authorization: Bearer <token>'."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


async def get_current_user(authorization: str | None) -> dict:
    """Valida el token de sesión y devuelve el usuario, o lanza 401."""
    token = _token_from_header(authorization)
    user = await db.get_user_by_token(token) if token else None
    if user is None:
        raise HTTPException(status_code=401, detail="sesión inválida o expirada")
    return user


# ---------------------------------------------------------------------------
# Lógica de un mensaje: cifrar -> firmar -> guardar -> verificar
# ---------------------------------------------------------------------------
async def process_message(sender: str, plaintext: str) -> dict:
    """Pasos 2 a 6 del flujo esperado."""
    # PASO 2a: CIFRADO — POST /confidentiality/encrypt
    ciphertext = await cia_client.encrypt(plaintext)

    # PASO 2b: FIRMA — POST /integrity/sign (firma HMAC asociada al mensaje)
    firma = await cia_client.sign(plaintext)

    # PASO 3: GUARDADO EN BD — ciphertext + firma + remitente + timestamp
    row = await db.create_message(sender, ciphertext, firma)

    # PASO 5: DESCIFRADO — POST /confidentiality/decrypt para mostrar el texto
    row["plaintext"] = await cia_client.decrypt(row["ciphertext"])
    row["firma"] = None  # no exponer la firma en el chat
    return row


async def validate_and_notify(message_id: int) -> None:
    """Espera, luego PASO 6: verifica la integridad y notifica el nuevo estado."""
    await asyncio.sleep(1.2)
    row = await db.get_message(message_id)
    plaintext = await cia_client.decrypt(row["ciphertext"])
    # VERIFICACIÓN — POST /integrity/verify sobre (texto plano, firma)
    valid = await cia_client.verify(plaintext, row["firma"])
    status = MENSAJE_VERIFICADO if valid else VERIFICACION_FALLIDA
    await db.update_status(message_id, status)
    await broadcast({"type": "status_update", "id": message_id, "status": status})


# ---------------------------------------------------------------------------
# REST
# ---------------------------------------------------------------------------
@app.post("/api/register")
async def register(payload: RegisterRequest):
    """REGISTRO — crea una cuenta. Guarda solo el hash de la contraseña."""
    username = payload.username.strip()
    if not username or not payload.password:
        raise HTTPException(status_code=400, detail="usuario y contraseña obligatorios")
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="la contraseña debe tener al menos 4 caracteres")
    user = await db.create_user(username, auth.hash_password(payload.password))
    if user is None:
        raise HTTPException(status_code=409, detail="el usuario ya existe")
    return {"message": "usuario registrado", "username": user["username"]}


@app.post("/api/login")
async def login(payload: LoginRequest):
    """LOGIN — verifica la contraseña y devuelve un token de sesión."""
    user = await db.get_user_by_username(payload.username.strip())
    if user is None or not auth.verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="usuario o contraseña incorrectos")
    token = auth.generate_token()
    await db.create_session(token, user["id"])
    return {"token": token, "username": user["username"]}


@app.post("/api/logout")
async def logout(authorization: str | None = Header(default=None)):
    """Cierra la sesión eliminando el token."""
    token = _token_from_header(authorization)
    if token:
        await db.delete_session(token)
    return {"message": "sesión cerrada"}


@app.get("/api/me")
async def me(authorization: str | None = Header(default=None)):
    """Valida el token guardado en el navegador (útil al recargar la página)."""
    user = await get_current_user(authorization)
    return {"username": user["username"]}


@app.post("/api/send")
async def send_message(payload: SendRequest, authorization: str | None = Header(default=None)):
    """Envía un mensaje: cifra/firma/guarda/verifica. El remitente sale del token."""
    user = await get_current_user(authorization)
    if not payload.message.strip():
        raise HTTPException(status_code=400, detail="mensaje vacío")
    row = await process_message(user["username"], payload.message.strip())
    return row


@app.get("/api/messages")
async def get_messages():
    """PASO 4: lee los mensajes desde la BD y los devuelve sin ciphertext/firma."""
    rows = await db.list_messages()
    for r in rows:
        r.pop("ciphertext", None)
        r.pop("firma", None)
    return rows


@app.get("/api/messages/{message_id}")
async def get_message(message_id: int):
    row = await db.get_message(message_id)
    if row is None:
        raise HTTPException(status_code=404, detail="mensaje no encontrado")
    row.pop("firma", None)
    return row


@app.post("/api/messages/{message_id}/validate")
async def validate(message_id: int):
    """Revalida un mensaje: descifra, llama a /integrity/verify y actualiza."""
    row = await db.get_message(message_id)
    if row is None:
        raise HTTPException(status_code=404, detail="mensaje no encontrado")
    try:
        plaintext = await cia_client.decrypt(row["ciphertext"])
    except ValueError:
        await db.update_status(message_id, VERIFICACION_FALLIDA)
        return {**row, "status": VERIFICACION_FALLIDA, "firma": None}
    valid = await cia_client.verify(plaintext, row["firma"])
    status = MENSAJE_VERIFICADO if valid else VERIFICACION_FALLIDA
    await db.update_status(message_id, status)
    return {**row, "status": status, "firma": None}


@app.get("/api/messages/{message_id}/plaintext")
async def get_plaintext(message_id: int):
    """PASO 5: muestra el texto descifrado vía POST /confidentiality/decrypt."""
    row = await db.get_message(message_id)
    if row is None:
        raise HTTPException(status_code=404, detail="mensaje no encontrado")
    try:
        plaintext = await cia_client.decrypt(row["ciphertext"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"id": row["id"], "plaintext": plaintext}


# ---------------------------------------------------------------------------
# WebSocket (tiempo real)
# ---------------------------------------------------------------------------
connections: dict[WebSocket, str] = {}


async def broadcast(payload: dict) -> None:
    dead = []
    for ws in list(connections):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        connections.pop(ws, None)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    # El remitente se obtiene del token de sesión (nunca se confía en el cliente)
    token = ws.query_params.get("token")
    user = await db.get_user_by_token(token) if token else None
    if user is None:
        await ws.send_json({"type": "error", "detail": "sesión inválida"})
        await ws.close()
        return
    username = user["username"]
    connections[ws] = username
    try:
        while True:
            data = await ws.receive_text()
            # Flujo completo: cifrar -> firmar -> guardar -> desplegar -> verificar
            row = await process_message(username, data)
            await broadcast({"type": "new_message", "message": row})
            asyncio.create_task(validate_and_notify(row["id"]))
    except WebSocketDisconnect:
        pass
    finally:
        connections.pop(ws, None)


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


@app.get("/")
async def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
