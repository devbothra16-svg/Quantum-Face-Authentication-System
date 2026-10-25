# Project conventions

- Python 3.11+, typed public interfaces, docstrings, deterministic seeds.
- Keep image bytes in memory only; persist encrypted cancelable embeddings only.
- Prefer small service functions and explicit configuration. Quantum paths must have a classical fallback.
- Format with Black and lint with Ruff. Add pytest coverage for security-sensitive behavior.
- Never commit datasets, model weights, secrets, local keys, or generated artifacts.
- Run `make test` after changes; `make eval` for evaluation changes.
