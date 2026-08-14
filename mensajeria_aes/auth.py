"""Autenticación: hash de contraseñas con PBKDF2 y tokens de sesión.

Nunca se guarda la contraseña en texto plano. Se guarda:
    pbkdf2_sha256$<iteraciones>$<salt_hex>$<hash_hex>

Al iniciar sesión se vuelve a calcular el hash con el mismo salt y se compara.
La sesión se identifica con un token aleatorio que se guarda en la BD.
"""

import hashlib
import os
import secrets

_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    """Genera el hash PBKDF2-SHA256 de una contraseña (con salt aleatorio)."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return f"pbkdf2_sha256${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Verifica una contraseña contra el hash guardado (comparación segura)."""
    try:
        algo, iterations, salt_hex, hash_hex = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return secrets.compare_digest(digest.hex(), hash_hex)
    except Exception:
        return False


def generate_token() -> str:
    """Genera un token de sesión aleatorio (imposible de adivinar)."""
    return secrets.token_urlsafe(32)
