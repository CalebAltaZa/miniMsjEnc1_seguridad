"""
cia_client.py — Cliente HTTP de la CIA API.

El chat NO cifra ni firma por su cuenta: consume la CIA API tal como fue
proporcionada, vía HTTP. Cada función corresponde a un endpoint:

    encrypt(texto)        -> POST /confidentiality/encrypt
    decrypt(ciphertext)   -> POST /confidentiality/decrypt
    sign(texto)           -> POST /integrity/sign
    verify(texto, firma)  -> POST /integrity/verify
"""

import os

import httpx

CIA_API_URL = os.environ.get("CIA_API_URL", "http://127.0.0.1:8000")

_client: httpx.AsyncClient | None = None


async def start_client() -> None:
    """Crea el cliente HTTP compartido (se llama al iniciar la app)."""
    global _client
    _client = httpx.AsyncClient(base_url=CIA_API_URL, timeout=10)


async def stop_client() -> None:
    """Cierra el cliente HTTP compartido (se llama al apagar la app)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def encrypt(message: str) -> str:
    """CIFRADO — llama a POST /confidentiality/encrypt y devuelve el ciphertext."""
    resp = await _client.post("/confidentiality/encrypt", json={"message": message})
    resp.raise_for_status()
    return resp.json()["ciphertext"]


async def decrypt(ciphertext: str) -> str:
    """DESCIFRADO — llama a POST /confidentiality/decrypt y devuelve el texto plano."""
    resp = await _client.post("/confidentiality/decrypt", json={"ciphertext": ciphertext})
    if resp.status_code == 403:
        raise ValueError("ciphertext inválido o manipulado — acceso denegado por la CIA API")
    resp.raise_for_status()
    return resp.json()["plaintext"]


async def sign(message: str) -> str:
    """FIRMA — llama a POST /integrity/sign y devuelve la firma HMAC asociada."""
    resp = await _client.post("/integrity/sign", json={"message": message})
    resp.raise_for_status()
    return resp.json()["signature"]


async def verify(message: str, signature: str) -> bool:
    """VERIFICACIÓN — llama a POST /integrity/verify; True si valid == true."""
    resp = await _client.post(
        "/integrity/verify", json={"message": message, "signature": signature}
    )
    resp.raise_for_status()
    return resp.json()["valid"]
