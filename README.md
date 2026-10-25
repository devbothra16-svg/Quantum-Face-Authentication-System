# Quantum Face Auth

CPU-first research scaffold for cloud-hosted biometric authentication. It includes a FastAPI service, encrypted cancelable-template primitives, a React webcam interface, optional quantum optimization interfaces, PostgreSQL/Redis Compose services, and documentation.

## Run

1. Install Docker Compose v2.
2. Copy `.env.example` to `.env` and change local-only credentials.
3. Run `docker compose up --build` and open `https://localhost` (accept the development self-signed certificate warning).

The interactive demo currently uses a deterministic synthetic image embedding and a challenge placeholder. It is not a working secure face-recognition or liveness system. See [DECISIONS](docs/DECISIONS.md).

For local backend development: `python -m venv .venv`, activate it, `pip install -e '.[dev]'`, then `uvicorn app.main:app --app-dir backend --reload`.

To apply schema migrations explicitly, run `alembic upgrade head`. The app also creates tables on startup for the local demo.

## Evaluation

`make eval` reproduces a synthetic metrics smoke check and writes `docs/RESULTS.md`. It is deliberately labeled and must not be interpreted as biometric performance. LFW extraction and real FaceNet evaluation remain unimplemented pending model and dataset provisioning.

## Quantum switches

Set `USE_QUANTUM=true` to enable optional quantum path hooks. `QUANTUM_BACKEND=simulator` is the only implemented path; `ibm` is an integration placeholder and is never enabled by default. Classical mutual-information selection and cosine comparison are available fallbacks.

## Security posture

Images are not database fields. Stored templates are AES-GCM ciphertext and user-specific projected vectors. The local key adapter, process-local nonce check, and generated signing keys are development-only. Do not deploy until the remaining work in [Threat Model](docs/THREAT_MODEL.md) is complete.

## Research report outline

Abstract; literature gap; consented dataset and subject-disjoint protocol; embedding and liveness methodology; classical and quantum methods; ROC/EER/FAR/FRR and latency results; ablations; limitations, privacy risks, and future work.
