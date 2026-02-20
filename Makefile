.PHONY: aws

aws:
	docker compose run --rm aws /bin/bash
gastown:
	docker compose run --rm aws bash -lc "cd gastown && uv run cdk deploy --require-approval never && uv run ../scripts/check_instance.py"
