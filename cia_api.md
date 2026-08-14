# CIA Triad Demo API — curl Examples

These examples assume the server is running locally:

```bash
pip install fastapi "uvicorn[standard]" cryptography
uvicorn cia_api:app --reload
```

Base URL: `http://127.0.0.1:8000`

---

## Confidentiality

### Encrypt a message
```bash
curl -X POST http://127.0.0.1:8000/confidentiality/encrypt \
  -H "Content-Type: application/json" \
  -d '{"message": "The midterm exam covers Nmap and Wireshark."}'
```
Response:
```json
{"ciphertext": "gAAAAABqe5VY..."}
```

### Decrypt a message
Use the `ciphertext` returned above:
```bash
curl -X POST http://127.0.0.1:8000/confidentiality/decrypt \
  -H "Content-Type: application/json" \
  -d '{"ciphertext": "gAAAAABqe5VY..."}'
```

### Decrypt with an invalid ciphertext (simulates an attacker → should return `403`)
```bash
curl -i -X POST http://127.0.0.1:8000/confidentiality/decrypt \
  -H "Content-Type: application/json" \
  -d '{"ciphertext": "this-is-not-a-valid-token"}'
```

---

## Integrity

### Sign a message
```bash
curl -X POST http://127.0.0.1:8000/integrity/sign \
  -H "Content-Type: application/json" \
  -d '{"message": "Transfer $500.00 to account 1234"}'
```
Response:
```json
{"message": "Transfer $500.00 to account 1234", "signature": "1451221f..."}
```

### Verify an unmodified message (→ `valid: true`)
```bash
curl -X POST http://127.0.0.1:8000/integrity/verify \
  -H "Content-Type: application/json" \
  -d '{"message": "Transfer $500.00 to account 1234", "signature": "1451221f..."}'
```

### Verify a tampered message (→ `valid: false`)
```bash
curl -X POST http://127.0.0.1:8000/integrity/verify \
  -H "Content-Type: application/json" \
  -d '{"message": "Transfer $5000.00 to account 1234", "signature": "1451221f..."}'
```

---

## Availability

### Check the status of all redundant nodes
```bash
curl http://127.0.0.1:8000/availability/status
```

### Simulate a request with automatic failover
Run this a few times in a row — you'll sometimes get `200` with the node that served it, and sometimes `503` when every node is down:
```bash
curl -i http://127.0.0.1:8000/availability/request
```

---

## Root

```bash
curl http://127.0.0.1:8000/
```