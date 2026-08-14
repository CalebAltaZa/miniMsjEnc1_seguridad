# Práctica: Chat Seguro con Cifrado y Verificación de Integridad
### Basado en CIA API (FastAPI)

## Descripción General
El estudiante desarrollará una aplicación de chat que use la CIA API (`cia_api.py`) para cifrar y verificar la integridad de los mensajes entre al menos 2 usuarios. Los mensajes deben guardarse en una base de datos, desde donde se consultará la información para desplegarla en el chat.

## Requisitos Funcionales

- Debe soportar como mínimo **2 usuarios** que puedan enviarse mensajes entre sí.
- Cada mensaje enviado debe **cifrarse** con `POST /confidentiality/encrypt` antes de guardarse.
- Cada mensaje enviado debe **firmarse** con `POST /integrity/sign`, generando una firma asociada.
- El mensaje (cifrado + firma + remitente + timestamp) debe **guardarse en una base de datos**, no solo mantenerse en memoria.
- El chat debe **leer los mensajes desde la base de datos** para desplegarlos en pantalla (no directamente desde la sesión en memoria).
- Al desplegarse por primera vez, el mensaje debe mostrar la leyenda **"No verificado"**.
- La aplicación debe llamar a `POST /integrity/verify`; si responde `valid: true`, la leyenda debe cambiar a **"Mensaje verificado"**.
- El texto mostrado al usuario debe ser el descifrado (`POST /confidentiality/decrypt`), nunca el cifrado.

## Requisitos Técnicos

- Usar la CIA API tal como fue proporcionada (se puede extender, pero sin quitar el cifrado, firma y verificación).
- Base de datos libre: SQLite, PostgreSQL, MySQL, etc. — la que el estudiante prefiera.
- Cliente de chat con la tecnología de preferencia (HTML/JS, Python, consola, etc.), siempre consumiendo la API vía HTTP.
- El código debe estar comentado señalando dónde se cifra, firma, guarda en BD y verifica.

## Flujo de Funcionamiento Esperado

1. El Usuario A escribe y envía un mensaje.
2. La app llama a `/confidentiality/encrypt` y `/integrity/sign`.
3. El mensaje cifrado, su firma, remitente y timestamp se **guardan en la base de datos**.
4. La app consulta la base de datos y despliega el mensaje con la leyenda **"No verificado"**.
5. La app descifra el mensaje (`/confidentiality/decrypt`) para mostrar el texto plano.
6. La app llama a `/integrity/verify`; si `valid: true`, la leyenda cambia a **"Mensaje verificado"**.

## Entregables

- Código fuente completo (cliente, base de datos y API si fue modificada).
- Script o modelo de la base de datos utilizada.
- README breve explicando cómo ejecutar la aplicación.