ACTION := START

.PHONY: aws

aws:
	docker compose run --rm aws /bin/bash
gastown:
ifeq ($(ACTION),START)
	docker compose run --rm aws bash -lc "cd gastown && uv run cdk deploy --require-approval never && uv run ../scripts/check_instance.py"
else ifeq ($(ACTION),STOP)
	docker compose run --rm aws bash -lc "cd gastown && uv run cdk destroy --force"
else
	@echo "Invalid ACTION=$(ACTION)"
endif
