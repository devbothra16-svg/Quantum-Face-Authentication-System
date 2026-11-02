# Architecture

```mermaid
flowchart LR
  Browser[React webcam UI + local face mesh] -->|ephemeral frames + one-use challenge ID| Proxy[Nginx]
  Proxy --> API[FastAPI]
  API --> Vision[Vision/liveness service]
  API --> Protect[Cancelable projection + AES-GCM]
  Protect --> DB[(PostgreSQL encrypted templates + audit)]
  API --> Cache[(Redis; one-use face challenges + rate limit)]
  API --> Quantum[QUBO / VQC optional simulator]
  API --> JWT[Short-lived RS256 token]
```

The browser's face-mesh model runs locally and draws a live guide. The API accepts base64 frame payloads but deliberately does not persist them. Deployments should terminate TLS at the proxy and set restrictive CORS origins.
