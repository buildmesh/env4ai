ACTION := START
.DEFAULT_GOAL := interactive
DOCKER_COMPOSE_RUN := docker compose run --rm \
	-e AWS_PROFILE \
	-e AWS_REGION \
	-e AWS_DEFAULT_REGION \
	-e CDK_DEFAULT_REGION \
	-e CDK_DEFAULT_ACCOUNT \
	-e AMI_LOAD \
	-e AMI_LIST \
	-e AMI_PICK \
	-e AMI_BOOTSTRAP \
	-e AMI_SAVE \
	-e AMI_TAG

.PHONY: interactive aws

interactive:
	$(DOCKER_COMPOSE_RUN) aws bash -lc "cd /home/user/gastown && uv run ../scripts/interactive_workstation.py"

aws:
	$(DOCKER_COMPOSE_RUN) aws /bin/bash
builder:
ifeq ($(ACTION),START)
	$(DOCKER_COMPOSE_RUN) aws bash -lc "cd /home/user/builder && uv run ../scripts/deploy_workstation.py --environment builder --stack-dir /home/user/builder --stack-name BuilderWorkstationStack"
else ifeq ($(ACTION),STOP)
	$(DOCKER_COMPOSE_RUN) aws bash -lc "cd /home/user/builder && uv run ../scripts/stop_workstation.py --environment builder --stack-dir /home/user/builder --stack-name BuilderWorkstationStack"
else
	@echo "Invalid ACTION=$(ACTION)"
endif
gastown:
ifeq ($(ACTION),START)
	$(DOCKER_COMPOSE_RUN) aws bash -lc "cd /home/user/gastown && uv run ../scripts/deploy_workstation.py --environment gastown --stack-dir /home/user/gastown --stack-name GastownWorkstationStack"
else ifeq ($(ACTION),STOP)
	$(DOCKER_COMPOSE_RUN) aws bash -lc "cd /home/user/gastown && uv run ../scripts/stop_workstation.py --environment gastown --stack-dir /home/user/gastown --stack-name GastownWorkstationStack"
else
	@echo "Invalid ACTION=$(ACTION)"
endif
test:
	cd aws/gastown && uv run python -m unittest discover -s tests/unit -v
