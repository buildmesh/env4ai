# Architecture Baseline

## System Overview

The repository provisions and manages AI-oriented EC2 workstation environments through a Dockerized local tooling workflow and an AWS CDK application.

## Top-Level Boundaries

- `aws/`: Infrastructure code and scripts.
- `openspec/`: Change artifacts and specs for planning and implementation workflow.
- `docs/`: Human-facing project documentation.
- `Makefile` + `docker-compose.yaml`: Primary local execution entrypoints.

## Module Responsibilities

### Local Tooling Entrypoints

- [`Makefile`](../../Makefile): Defines top-level commands (`make`, `make gastown`, `make test`).
- [`docker-compose.yaml`](../../docker-compose.yaml): Defines the `aws` tooling container, AWS config mount, and account secret wiring.
- [`aws/Dockerfile`](../../aws/Dockerfile): Builds the tooling container with `uv`, AWS CLI, SAM CLI, and AWS CDK.

### Environment-Specific Infrastructure Module

- [`aws/gastown/app.py`](../../aws/gastown/app.py): CDK app bootstrap and account/region resolution.
- [`aws/gastown/gastown_workstation/gastown_workstation_stack.py`](../../aws/gastown/gastown_workstation/gastown_workstation_stack.py): CDK stack resource definitions for workstation infrastructure.
- [`aws/gastown/environment_config.py`](../../aws/gastown/environment_config.py): Canonical `ENVIRONMENT_SPEC` for gastown (single source for environment knobs and derived names).
- [`aws/gastown/init/*.sh`](../../aws/gastown/init): User data provisioning scripts executed on workstation launch.
- [`aws/builder/environment_config.py`](../../aws/builder/environment_config.py): Canonical `ENVIRONMENT_SPEC` for builder.
- [`aws/scripts/check_instance.py`](../../aws/scripts/check_instance.py): Post-deploy helper to discover newest Spot Fleet instance and print SSH config guidance.

### Shared Cross-Environment Core (`aws/workstation_core/`)

- [`aws/workstation_core/environment_config.py`](../../aws/workstation_core/environment_config.py): Environment spec contracts (`EnvironmentSpec`, `AmiSelectorConfig`) and naming derivation helpers.
- [`aws/workstation_core/cdk_helpers.py`](../../aws/workstation_core/cdk_helpers.py): Shared CDK derivation helpers for AMI resolution, launch specification generation, and stack naming utilities.
- [`aws/workstation_core/ami_lifecycle.py`](../../aws/workstation_core/ami_lifecycle.py): Shared AMI save-on-stop primitives (instance resolution, create image, wait for availability).
- [`aws/workstation_core/orchestration.py`](../../aws/workstation_core/orchestration.py): Stop-time orchestration contracts and flow coordination.
- [`aws/workstation_core/runtime_resolution.py`](../../aws/workstation_core/runtime_resolution.py): Shared account/region and runtime context resolution helpers.

### Shared Script Entrypoints

- [`aws/scripts/deploy_workstation.py`](../../aws/scripts/deploy_workstation.py): Shared deploy entrypoint for AMI load/list/pick flows and IAM preflight behavior.
- [`aws/scripts/stop_workstation.py`](../../aws/scripts/stop_workstation.py): Shared stop entrypoint with AMI save-on-stop gating before destroy.

### Validation And Quality Checks

- [`aws/gastown/tests/unit/`](../../aws/gastown/tests/unit): Unit tests for region/account resolution and CDK stack behavior.
- `make test` runs unit tests through `uv` in `aws/gastown`.

### Planning And Change Management

- [`openspec/config.yaml`](../../openspec/config.yaml): OpenSpec configuration.
- [`openspec/changes/`](../../openspec/changes): Per-change proposal/spec/design/tasks and implementation progress.

## Dependency And Runtime Shape

1. Developer runs commands through the containerized toolchain.
2. Makefile target invokes shared script entrypoints (`deploy_workstation.py` / `stop_workstation.py`) with environment-specific stack coordinates.
3. Script entrypoints resolve canonical environment naming from `ENVIRONMENT_SPEC` where available.
4. CDK application in each environment directory synthesizes and deploys CloudFormation resources.
5. Post-deploy helper script discovers target EC2 instance metadata and prints connection instructions.

## Architectural Constraints

- AWS region/account resolution depends on environment variables and mounted AWS profile data (see `app.py` and `check_instance.py`).
- Workstation provisioning currently depends on Spot Fleet and an existing key pair name (`aws_key`) in target AWS account.
- SSH ingress is open to all IPv4 at stack level and should be reviewed for tighter controls in production-like usage.
