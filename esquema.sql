-- Esquema de la base de datos del Chat Seguro
-- PostgreSQL — tablas `users`, `sessions` y `messages`
--
-- users:    cuentas de usuario (solo se guarda el hash PBKDF2 de la contraseña)
-- sessions: tokens de sesión emitidos al iniciar sesión
-- messages: ciphertext (texto cifrado por la CIA API), firma (de
--           /integrity/sign), remitente y timestamp. El campo `status` inicia
--           en 'No verificado' y cambia a 'Mensaje verificado' cuando
--           /integrity/verify responde valid: true.

CREATE TABLE IF NOT EXISTS users (
    id            BIGSERIAL PRIMARY KEY,
    username      TEXT        NOT NULL UNIQUE,
    password_hash TEXT        NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    BIGINT      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id          BIGSERIAL PRIMARY KEY,                 -- identificador único
    sender      TEXT        NOT NULL,                  -- remitente (usuario)
    ciphertext  TEXT        NOT NULL,                  -- mensaje cifrado
    firma       TEXT        NOT NULL,                  -- firma HMAC del mensaje
    status      TEXT        NOT NULL DEFAULT 'No verificado',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()     -- timestamp
);
