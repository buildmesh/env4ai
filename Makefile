ACTION := START

.PHONY: aws

aws:
	docker compose run --rm aws /bin/bash
builder:
ifeq ($(ACTION),START)
	docker compose run --rm aws bash -lc "cd /home/user && uv run scripts/deploy_workstation.py --environment builder --stack-dir /home/user/builder --stack-name BuilderWorkstationStack"
else ifeq ($(ACTION),STOP)
	docker compose run --rm aws bash -lc "cd /home/user && uv run scripts/stop_workstation.py --environment builder --stack-dir /home/user/builder --stack-name BuilderWorkstationStack"
else
	@echo "Invalid ACTION=$(ACTION)"
endif
gastown:
ifeq ($(ACTION),START)
	docker compose run --rm aws bash -lc "cd /home/user && uv run scripts/deploy_workstation.py --environment gastown --stack-dir /home/user/gastown --stack-name GastownWorkstationStack"
else ifeq ($(ACTION),STOP)
	docker compose run --rm aws bash -lc "cd /home/user && uv run scripts/stop_workstation.py --environment gastown --stack-dir /home/user/gastown --stack-name GastownWorkstationStack"
else
	@echo "Invalid ACTION=$(ACTION)"
endif
test:
	cd aws/gastown && uv run python -m unittest discover -s tests/unit -v
