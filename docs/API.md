# API

- `GET /api/health`: local service status.
- `POST /api/face/challenge`: `{email}`. Returns a random, account-bound, single-use challenge that expires after two minutes.
- `POST /api/enroll`: `{full_name, email, department, employee_id, frames:[12 base64 JPEG frames], challenge_id, consent:true}`. Stores the company profile and an encrypted SFace embedding from centered frames after liveness succeeds; rejects an existing enrollment for that email. The demo does not verify profile fields against a company directory.
- `POST /api/auth`: same frame/challenge fields; returns a short-lived RS256 `access_token` only after the motion challenge and SFace cosine threshold both pass.
- `GET /api/users/me`: bearer-token audit history.
- `GET /api/vault`: sample workspace records, requires a valid bearer token. Records are fictional demo content.
- `POST /api/users/me/revoke`: revoke current template; re-enrollment creates a fresh transform secret.
- `DELETE /api/users/me`: erase template, audit events, and account.

YuNet detects one face per frame; SFace produces the identity embedding. The browser runs a local MediaPipe face-landmark model for the live mesh and pose guidance; captured images are still checked by the server. A random first-turn direction and one-use challenge reduce accidental sequence errors and trivial request replay, but are not presentation-attack detection: a crafted client or replayed video may still pass. Enrollment is self-service and email ownership is not verified. Do not rely on these endpoints to protect company-sensitive data or as production access control.
