# Infrastructure And Deployment Baseline

## Deployment Topology

The current deployment path provisions one AWS workstation environment (`gastown`) using CDK from a local Dockerized toolchain.

## Local Tooling Runtime

- Tooling container definition: [`docker-compose.yaml`](../../docker-compose.yaml)
- Tooling image build: [`aws/Dockerfile`](../../aws/Dockerfile)
- Mounted credentials/config:
  - `~/.aws` -> `/home/user/.aws`
  - `./secrets/aws_acct` -> `/run/secrets/aws_acct`

## CDK Stack Resources (Gastown)

Defined in [`aws/gastown/gastown_workstation/gastown_workstation_stack.py`](../../aws/gastown/gastown_workstation/gastown_workstation_stack.py):

- VPC with custom subnet configuration
- Internet gateway + route table + public subnet route
- Security group allowing inbound SSH (`tcp/22`) from `0.0.0.0/0`
- Ubuntu 22.04 AMI lookup (Canonical owner)
  - Deploy-time override supported through CDK context key `ami_id`
- Spot Fleet request with one `t3.xlarge` instance target
- Base64-encoded user data composed from `aws/gastown/init/*.sh`
- EBS root volume settings in launch specification

## AWS Account/Region Resolution

- Region resolution in [`aws/gastown/app.py`](../../aws/gastown/app.py):
  1. `CDK_DEFAULT_REGION`
  2. `AWS_PROFILE` + `~/.aws/config` profile region
- Account resolution in [`aws/gastown/app.py`](../../aws/gastown/app.py):
  1. `CDK_DEFAULT_ACCOUNT`
  2. `/run/secrets/aws_acct`

## Operational Entry Points

- Deploy/start: `make gastown` (`ACTION=START` default) via [`Makefile`](../../Makefile)
  - AMI controls: `AMI_LOAD`, `AMI_LIST`, `AMI_PICK` via [`aws/scripts/deploy_workstation.py`](../../aws/scripts/deploy_workstation.py)
- Destroy/stop: `make gastown ACTION=STOP`
  - No save-on-stop Make variable is currently implemented; AMI preservation requires manual EC2 `create-image` + `wait image-available` before destroy.
- Post-deploy instance lookup + SSH snippet:
  - [`aws/scripts/check_instance.py`](../../aws/scripts/check_instance.py)

## AMI Override Path And Rollback Notes

- Default behavior: stack uses Canonical Ubuntu AMI lookup when no explicit `ami_id` context is provided.
- Override behavior: deploy helper resolves or selects an AMI ID from environment-scoped AMIs, then passes `-c ami_id=<id>` to CDK deploy.
- List-only behavior: `AMI_LIST=1` prints available AMIs and exits before deploy.
- Guardrails:
  - `AMI_PICK=1` requires `AMI_LIST=1`
  - `AMI_LOAD` cannot be combined with `AMI_LIST`

Rollback (disable AMI lifecycle options):

- Ensure no AMI option env vars are active:
  - `unset AMI_LOAD AMI_LIST AMI_PICK`
- Run normal deploy entrypoint:
  - `make gastown`
- If rollback is needed in CI/automation, remove injected `AMI_*` variables from job/env configuration.
- Post-rollback expectation: no `ami_id` context is passed and stack returns to default Ubuntu AMI resolution.

## IAM And Security Artifacts

- Deployer policy template: [`aws/iam/gastown/deployer-policy.json`](../../aws/iam/gastown/deployer-policy.json)
- Spot fleet tagging role expectation is embedded in stack definition and must exist in target account.

## Infrastructure Constraints / Risks

- Broad SSH ingress is operationally simple but security-sensitive.
- Spot Fleet behavior and instance availability depend on regional capacity/pricing.
- Deployment relies on local credential/config correctness and mounted secrets.
- AMI listing can include non-`available` states (`pending`, `failed`); operators should deploy from `available` images only.
- AMI load fails fast when the exact `<environment>_<tag>` name is missing, which blocks deployment by design.

## Rollback Guidance

To revert to pre-AMI-option behavior:

1. Clear `AMI_LOAD`, `AMI_LIST`, and `AMI_PICK` from the shell/session.
2. Run deploy with `make gastown` so the stack uses default Ubuntu AMI resolution.
3. Run stop with `make gastown ACTION=STOP` (no AMI preservation automation in current Make flow).
