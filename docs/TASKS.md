# AWS Gastown Region Resolution Tasks

Use this checklist to track implementation progress for making region/AZ configuration dynamic from AWS config.

- [x] Task 1: Baseline and constraints capture
  - Confirmed hardcoded values:
    - `aws/gastown/app.py`: `cdk.Environment(... region=os.environ.get("CDK_DEFAULT_REGION", "us-west-2"))` hardcodes a fallback region.
    - `aws/gastown/aws_workstation/aws_workstation_stack.py`: `availability_zone="us-west-2a"` hardcodes subnet AZ.
  - Captured acceptance criteria for this task stream:
    - No hardcoded region or AZ literals in resolution/runtime paths.
    - Deterministic precedence for region/account/profile resolution.
    - Clear, actionable failure messages for missing required config.
    - Unit tests cover expected, edge, and failure scenarios and pass.

- [x] Task 2: Region/account resolution contract (implementation-ready)
  - Finalized explicit precedence:
    - Region resolution:
      1. `CDK_DEFAULT_REGION` (trimmed, non-empty) wins.
      2. Else load `~/.aws/config` and resolve active profile section.
      3. Else raise `RuntimeError`.
    - Profile resolution:
      1. `AWS_PROFILE` (trimmed, non-empty).
      2. Else `default`.
      3. Section mapping in `~/.aws/config`:
         - `default` -> `[default]`
         - non-default profile `<name>` -> `[profile <name>]`
    - Account resolution:
      1. `CDK_DEFAULT_ACCOUNT` (trimmed, non-empty) wins.
      2. Else `/run/secrets/aws_acct` contents (trimmed, non-empty).
      3. Else raise `RuntimeError`.
  - Exact error strings (must match in tests):
    - Missing AWS config file:
      - `Unable to resolve AWS region: ~/.aws/config was not found and CDK_DEFAULT_REGION is not set.`
    - Missing profile section in AWS config:
      - `Unable to resolve AWS region: profile section '[{section_name}]' was not found in ~/.aws/config.`
    - Missing region key in resolved profile section:
      - `Unable to resolve AWS region: no 'region' value found in profile '[{profile_name}]' in ~/.aws/config.`
    - Missing account from both env and secret:
      - `Unable to resolve AWS account: CDK_DEFAULT_ACCOUNT is not set and /run/secrets/aws_acct is missing or empty.`

- [x] Task 3: Refactor `app.py` into testable helpers
  - Add small pure helpers (`get_profile_name`, config-section resolver, region loader, `get_region`, `get_account`).
  - Replace current `cdk.Environment(...)` wiring with resolved values only.
  - Remove silent fallback to `us-west-2`.

- [x] Task 4: Make stack AZ region-agnostic
  - In `aws/gastown/aws_workstation/aws_workstation_stack.py`, replace hardcoded subnet AZ with dynamic AZ selection (`Fn.get_azs` + `Fn.select`).
  - Ensure no region-specific literals remain for AZ/local-zone placement.

- [x] Task 5: Add resolver unit tests (new test module)
  - Expected case: default profile region read from config.
  - Edge case: non-default profile via `AWS_PROFILE`.
  - Failure case: no env region and no usable config region raises `RuntimeError`.
  - Include tests for missing profile section and missing config file behavior.

- [ ] Task 6: Upgrade stack tests from placeholder to real assertions
  - Assert synthesized subnet AZ is tokenized/dynamic, not a fixed `us-west-2*` literal.
  - Keep assertions resilient (resource-property checks, no brittle full-template snapshots).

- [ ] Task 7: Validate behavior with command-level checks
  - Run unit tests for `aws/gastown/tests/unit`.
  - Run `uv run cdk synth` in `aws/gastown` for:
    - env-region override success,
    - config-region success,
    - missing-region failure with expected error.

- [ ] Task 8: Documentation update and closeout
  - Update `README.md` with region/account precedence and profile examples.
  - Add an operational note that synth/deploy fails fast when active profile lacks `region`.
  - Final checklist pass against acceptance criteria.
