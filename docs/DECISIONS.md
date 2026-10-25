# Decisions and implementation limits

- This folder was empty and was not a Git checkout. The project is initialized here as a new repository.
- The implementation is a research/demo scaffold. The included image-to-vector and liveness services are explicitly non-biometric demos: raw bytes are decoded only transiently, hashed to a deterministic synthetic vector, and not stored. A matching model and true blink/head-motion validation remain required before any real identity use.
- FaceNet weights and LFW are not bundled. Model downloads and dataset licensing/consent are explicit prerequisites for meaningful evaluation. `make eval` currently prints a deterministic synthetic plumbing check and labels it as such; these values are not facial-recognition results.
- Quantum selection currently has an exact small-instance QUBO solver and greedy/MI fallback. Qiskit QAOA and PennyLane dependencies are optional, but production QAOA circuit construction and trained VQC are not yet integrated. The UI defaults to classical mode.
- Redis is included in Compose, but current nonce storage is process-local and rate limiting is not wired. Replace with Redis atomic `SET NX EX` and rate-limit middleware before deployment.
- Local keys are generated into a Docker named volume and are for development only. `AWSKMSAdapter` documents the integration boundary, not a working cloud implementation. RSA keys are generated on startup for local demonstration; production keys must be provisioned in managed KMS/HSM.
- Docker is not available in the authoring environment, so Compose could not be brought up here. Compose generates a self-signed localhost certificate at Nginx image build time; browsers will require a trust exception. Replace it with managed certificates outside development.
- The requested commit-per-phase workflow is represented by Git commits where feasible; incomplete phases are not represented as production-complete.
