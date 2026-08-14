"""Conexión a PostgreSQL y consultas de la tabla `messages`.

El chat guarda, por cada mensaje: ciphertext (ya cifrado por la CIA API),
firma (generada por /integrity/sign), remitente y timestamp. La validación
(/integrity/verify) se hace en app.py; aquí solo se actualiza el estado.
"""

import os

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

DSN = os.environ.get(
    "MENSAJERIA_DSN",
    "postgresql://postgres:postgres@localhost:5432/mensajeria",
)

# Esquema de la base de datos: ciphertext + firma + remitente + timestamp.
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id           BIGSERIAL PRIMARY KEY,
    username     TEXT        NOT NULL UNIQUE,
    password_hash TEXT       NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    token       TEXT PRIMARY KEY,
    user_id     BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id          BIGSERIAL PRIMARY KEY,
    sender      TEXT        NOT NULL,
    ciphertext  TEXT        NOT NULL,
    firma       TEXT        NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'No verificado',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

pool = AsyncConnectionPool(DSN, min_size=1, max_size=5, open=False)


async def init_db() -> None:
    """Crea la tabla si no existe y abre el pool de conexiones."""
    await pool.open()
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        await conn.execute(SCHEMA)


def _row_to_dict(row) -> dict:
    return {
        "id": row["id"],
        "sender": row["sender"],
        "ciphertext": row["ciphertext"],
        "firma": row["firma"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat(),
    }


async def create_message(sender: str, ciphertext: str, firma: str) -> dict:
    """GUARDADO EN BD — inserta ciphertext, firma, remitente y timestamp."""
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        cur = await conn.execute(
            """
            INSERT INTO messages (sender, ciphertext, firma)
            VALUES (%s, %s, %s)
            RETURNING id, sender, ciphertext, firma, status, created_at
            """,
            (sender, ciphertext, firma),
        )
        return _row_to_dict(await cur.fetchone())


async def get_message(message_id: int) -> dict | None:
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        cur = await conn.execute(
            "SELECT id, sender, ciphertext, firma, status, created_at "
            "FROM messages WHERE id = %s",
            (message_id,),
        )
        row = await cur.fetchone()
    return _row_to_dict(row) if row else None


async def list_messages() -> list[dict]:
    """LECTURA DESDE BD — devuelve todos los mensajes para desplegarlos."""
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        cur = await conn.execute(
            "SELECT id, sender, ciphertext, firma, status, created_at "
            "FROM messages ORDER BY id"
        )
        rows = await cur.fetchall()
    return [_row_to_dict(r) for r in rows]


async def update_status(message_id: int, status: str) -> None:
    """Actualiza el estado tras la verificación de integridad."""
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        await conn.execute(
            "UPDATE messages SET status = %s WHERE id = %s",
            (status, message_id),
        )


# ---------------------------------------------------------------------------
# Usuarios y sesiones
# ---------------------------------------------------------------------------
async def create_user(username: str, password_hash: str) -> dict | None:
    """REGISTRO — crea un usuario. Devuelve None si el usuario ya existe."""
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        try:
            cur = await conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) "
                "RETURNING id, username, created_at",
                (username, password_hash),
            )
            return await cur.fetchone()
        except Exception:
            return None


async def get_user_by_username(username: str) -> dict | None:
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        cur = await conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = %s",
            (username,),
        )
        return await cur.fetchone()


async def create_session(token: str, user_id: int) -> None:
    """Guarda una sesión: token aleatorio asociado a un usuario."""
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        await conn.execute(
            "INSERT INTO sessions (token, user_id) VALUES (%s, %s)",
            (token, user_id),
        )


async def get_user_by_token(token: str) -> dict | None:
    """Valida un token de sesión y devuelve el usuario correspondiente."""
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        cur = await conn.execute(
            """
            SELECT u.id, u.username
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token = %s
            """,
            (token,),
        )
        return await cur.fetchone()


async def delete_session(token: str) -> None:
    """Cierra la sesión (logout)."""
    async with pool.connection() as conn:
        conn.row_factory = dict_row
        await conn.execute("DELETE FROM sessions WHERE token = %s", (token,))
