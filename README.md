# Quantum Face Auth

CPU-first research scaffold for cloud-hosted biometric authentication. It includes a FastAPI service, encrypted cancelable-template primitives, a React webcam interface, optional quantum optimization interfaces, PostgreSQL/Redis Compose services, and documentation.

## Run

1. Install Docker Compose v2.
2. Copy `.env.example` to `.env` and change local-only credentials.
3. Run `docker compose up --build` and open `http://localhost:5173`.

The local demo uses OpenCV YuNet for server-side face detection, SFace for face embeddings, and MediaPipe Face Landmarker in the browser for a live connected-dot mesh and pose guide. Enrollment is a two-step flow: collect a user's name, company email, department, and employee ID, then guide them through the face scan. The profile and encrypted face template are saved together only after the scan succeeds. The browser asks you to hold center, follow an arrow to turn to each side, and return to center. It samples only the centered frames for identity matching, then unlocks the app workspace automatically when the server confirms both the movement challenge and the registered face. The image frames are processed by the local browser/backend and are not saved. The movement challenge is not certified presentation-attack detection; a crafted client or replayed video may still pass. The demo does not verify profile fields against an official company directory, and it lacks robust account recovery and independent biometric accuracy/bias testing. Never connect it to real company-sensitive data or use it for consequential access control.

For a demo, use **Enroll** and complete step 1 with the person's name, company email, department, and employee ID. Continue to step 2, allow camera access, check the biometric consent box, and register the face. The profile and encrypted template are stored together only after a successful scan. The app then issues a short setup session. In **Dashboard**, select **Set up Windows Hello / passkey** and follow the Windows prompt. Later, choose **Login**, enter the same email, and select **Continue with Windows Hello / passkey**. Windows may verify you with face, fingerprint, or device PIN; the biometric never reaches the server. The app stores the passkey public key. The webcam remains available as a fallback. `http://localhost:5173` uses the secure localhost origin required by browser camera and passkey APIs without the self-signed certificate warning. The first Docker build downloads the pinned, checksum-verified OpenCV Zoo face models. The frontend downloads the MediaPipe face-landmarker model on first startup; this requires internet access and the model file is kept out of Git.

For local backend development: `python -m venv .venv`, activate it, `pip install -e '.[dev]'`, then `uvicorn app.main:app --app-dir backend --reload`.

To apply schema migrations explicitly, run `alembic upgrade head`. The app also creates tables on startup for the local demo.

## Evaluation

`make eval` reproduces a synthetic metrics smoke check and writes `docs/RESULTS.md`. It is deliberately labeled and must not be interpreted as biometric performance. LFW extraction and real FaceNet evaluation remain unimplemented pending model and dataset provisioning.

## Quantum switches

Set `USE_QUANTUM=true` to enable optional quantum path hooks. `QUANTUM_BACKEND=simulator` is the only implemented path; `ibm` is an integration placeholder and is never enabled by default. Classical mutual-information selection and cosine comparison are available fallbacks.

## Security posture

Images are not database fields. Stored templates are AES-GCM ciphertext and user-specific projected vectors. The local key adapter and generated signing keys are development-only. Do not deploy until the remaining work in [Threat Model](docs/THREAT_MODEL.md) is complete. Head-motion checks can be replayed or spoofed and are not a substitute for certified presentation-attack detection.

## Research report outline

Abstract; literature gap; consented dataset and subject-disjoint protocol; embedding and liveness methodology; classical and quantum methods; ROC/EER/FAR/FRR and latency results; ablations; limitations, privacy risks, and future work.
