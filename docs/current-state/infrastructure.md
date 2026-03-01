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
- Destroy/stop: `make gastown ACTION=STOP`
- Post-deploy instance lookup + SSH snippet:
  - [`aws/scripts/check_instance.py`](../../aws/scripts/check_instance.py)

## IAM And Security Artifacts

- Deployer policy template: [`aws/iam/gastown/deployer-policy.json`](../../aws/iam/gastown/deployer-policy.json)
- Spot fleet tagging role expectation is embedded in stack definition and must exist in target account.

## Infrastructure Constraints / Risks

- Broad SSH ingress is operationally simple but security-sensitive.
- Spot Fleet behavior and instance availability depend on regional capacity/pricing.
- Deployment relies on local credential/config correctness and mounted secrets.
