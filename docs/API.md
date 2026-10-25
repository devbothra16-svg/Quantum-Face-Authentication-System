# API

- `GET /api/health`: local service status.
- `POST /api/enroll`: `{email, frames:[base64 JPEG...], nonce, challenge, consent:true}`.
- `POST /api/auth`: same frame/challenge fields; returns short-lived RS256 `access_token` on match.
- `GET /api/users/me`: bearer-token audit history.
- `POST /api/users/me/revoke`: revoke current template; re-enrollment creates a fresh transform secret.
- `DELETE /api/users/me`: erase template, audit events, and account.

The demo's challenge is not actually validated against observed landmarks, and the embedding fallback is not a face model. Do not rely on the current endpoints for biometric authentication.
