# Threat model

| Threat | Demo mitigation | Remaining work |
|---|---|---|
| Template theft | AES-256-GCM at rest; per-user cancelable projection | Managed KMS envelope encryption, key rotation and access policies |
| Replay | Nonce required and checked once | Process-local set is not multi-worker safe; use Redis TTL atomic writes |
| Spoofing | Challenge string and multi-frame requirement | Implement MediaPipe landmark blink/motion verification and texture checks |
| MITM | Nginx reverse proxy | TLS listener/certificates are not configured in this demo |
| Hill climbing | Short token expiry and generic auth failure | Rate limiting, lockouts, anomaly detection and score blinding |
| Data retention | No image database fields; explicit erase endpoint | Verify logs/proxies do not retain request bodies; define backups/deletion lifecycle |
| Account takeover | RS256 short-lived bearer tokens | Refresh-token rotation, revocation, stronger account proofing and admin authorization |

Biometric identifiers are sensitive and cannot be rotated like passwords. Do not deploy this prototype for access control or consequential identity decisions.
