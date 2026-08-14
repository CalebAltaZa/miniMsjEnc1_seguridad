"""
cia_api.py
==========

A minimal FastAPI service that demonstrates the CIA triad through 3 sets
of endpoints — one per principle. Open /docs after running it and you get
an interactive page where you can call each endpoint and see the concept
in action.

    C - Confidentiality : /confidentiality/*  -> encrypt/decrypt data
    I - Integrity        : /integrity/*        -> sign/verify data
    A - Availability      : /availability/*     -> simulated redundant nodes

Run it:
    pip install fastapi "uvicorn[standard]" cryptography
    uvicorn cia_api:app --reload

Then open:
    http://127.0.0.1:8000/docs
"""

import hashlib
import hmac
import os
import pathlib
import random

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from cryptography.fernet import Fernet, InvalidToken

app = FastAPI(
    title="CIA Triad Demo API",
    description="A tiny API that demonstrates Confidentiality, Integrity and Availability.",
    version="1.0.0",
)

# CORS: permite que cualquier cliente (incluida la página web del chat)
# consuma la API directamente desde el navegador vía HTTP.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Server-side secrets. En un sistema real viven en un gestor de secretos / KMS;
# aquí se persisten en archivos locales (.cia_keys/) para que los mensajes
# cifrados sigan siendo legibles entre reinicios del servicio.
# ---------------------------------------------------------------------------
_KEYS_DIR = pathlib.Path(__file__).resolve().parent / ".cia_keys"


def _load_or_create(name: str, generate):
    key_file = _KEYS_DIR / name
    if key_file.exists():
        return key_file.read_bytes()
    _KEYS_DIR.mkdir(exist_ok=True)
    key = generate()
    key_file.write_bytes(key)
    return key


ENCRYPTION_KEY = _load_or_create("fernet.key", Fernet.generate_key)
_cipher = Fernet(ENCRYPTION_KEY)

SIGNING_KEY = _load_or_create("signing.key", lambda: os.urandom(32))

# Simulated redundant backend nodes for the Availability demo.
NODES = ["server-1", "server-2", "server-3"]
NODE_RELIABILITY = 0.55  # probability that a given node is UP on a given check


# ===========================================================================
# C — CONFIDENTIALITY  (only holders of the key can read the data)
# ===========================================================================
class EncryptRequest(BaseModel):
    message: str


class EncryptResponse(BaseModel):
    ciphertext: str


class DecryptRequest(BaseModel):
    ciphertext: str


class DecryptResponse(BaseModel):
    plaintext: str


@app.post("/confidentiality/encrypt", response_model=EncryptResponse, tags=["Confidentiality"])
def encrypt(payload: EncryptRequest):
    """Encrypts a message. Without the server's key, the result is unreadable."""
    token = _cipher.encrypt(payload.message.encode())
    return EncryptResponse(ciphertext=token.decode())


@app.post("/confidentiality/decrypt", response_model=DecryptResponse, tags=["Confidentiality"])
def decrypt(payload: DecryptRequest):
    """Decrypts a message using the server's key. Invalid/foreign ciphertext is rejected."""
    try:
        plaintext = _cipher.decrypt(payload.ciphertext.encode())
    except InvalidToken:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid ciphertext or wrong key — access denied.",
        )
    return DecryptResponse(plaintext=plaintext.decode())


# ===========================================================================
# I — INTEGRITY  (data is accurate and hasn't been tampered with)
# ===========================================================================
class SignRequest(BaseModel):
    message: str


class SignResponse(BaseModel):
    message: str
    signature: str


class VerifyRequest(BaseModel):
    message: str
    signature: str


class VerifyResponse(BaseModel):
    valid: bool


def _sign(message: str) -> str:
    return hmac.new(SIGNING_KEY, message.encode(), hashlib.sha256).hexdigest()


@app.post("/integrity/sign", response_model=SignResponse, tags=["Integrity"])
def sign(payload: SignRequest):
    """Signs a message with HMAC-SHA256 so any later tampering can be detected."""
    return SignResponse(message=payload.message, signature=_sign(payload.message))


@app.post("/integrity/verify", response_model=VerifyResponse, tags=["Integrity"])
def verify(payload: VerifyRequest):
    """Verifies whether a (message, signature) pair is untampered.

    Try it two ways:
    1. Use the exact message + signature from /integrity/sign  -> valid: true
    2. Change even one character of the message                -> valid: false
    """
    expected = _sign(payload.message)
    is_valid = hmac.compare_digest(expected, payload.signature)
    return VerifyResponse(valid=is_valid)


# ===========================================================================
# A — AVAILABILITY  (the service stays reachable even if parts fail)
# ===========================================================================
class NodeStatus(BaseModel):
    name: str
    status: str


class StatusResponse(BaseModel):
    nodes: list[NodeStatus]


class RequestResponse(BaseModel):
    served_by: str


@app.get("/availability/status", response_model=StatusResponse, tags=["Availability"])
def availability_status():
    """Shows a fresh up/down check for every redundant node."""
    nodes = [
        NodeStatus(name=n, status="UP" if random.random() < NODE_RELIABILITY else "DOWN")
        for n in NODES
    ]
    return StatusResponse(nodes=nodes)


@app.get("/availability/request", response_model=RequestResponse, tags=["Availability"])
def availability_request():
    """Simulates an incoming request with automatic failover across nodes.

    Each node has a chance of being down. The request is routed to the first
    node that responds. If every node is down, the service returns 503 —
    call this endpoint a few times to see both outcomes.
    """
    for node in NODES:  # try nodes in order — this is the failover sequence
        if random.random() < NODE_RELIABILITY:
            return RequestResponse(served_by=node)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="All redundant nodes are down — service unavailable.",
    )


# ===========================================================================
# Root
# ===========================================================================
@app.get("/", tags=["Root"])
def root():
    return {
        "message": "CIA Triad Demo API — open /docs to try each endpoint interactively.",
        "principles": {
            "confidentiality": "/confidentiality/encrypt, /confidentiality/decrypt",
            "integrity": "/integrity/sign, /integrity/verify",
            "availability": "/availability/status, /availability/request",
        },
    }