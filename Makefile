.PHONY: setup test demo install run

setup:
	@test -f .env || cp .env.example .env
	@echo "Edit .env with your New Relic credentials, then: source .env (or 'set -a && source .env && set +a')"

test:
	python3 -m unittest discover tests

demo:
	python3 -m ai_readiness --mock --mock-scenario mature --account-id 0 --output table

install:
	pip install -e .

run:
	python3 -m ai_readiness
