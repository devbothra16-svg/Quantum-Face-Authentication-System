.PHONY: dev test eval lint format
dev:
	docker compose up --build
test:
	python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=80
eval:
	python -m ml.train_eval.evaluate --output docs/RESULTS.md
lint:
	ruff check backend ml
format:
	black backend ml
