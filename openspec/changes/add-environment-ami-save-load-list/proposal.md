## Why

The current environment lifecycle always starts from the base Ubuntu AMI and re-runs bootstrap, which increases deploy time and loses useful in-instance state across stop/start cycles. Adding AMI save/load workflows lets users preserve known-good environments and restart from them quickly with explicit version tags.

## What Changes

- Add a stop-time option to save the running instance as an AMI before `cdk destroy`.
- Support user-provided save tags so images are named `<environment>_<tag>` (for example, `gastown_20260228`).
- Add a deploy-time option to load a previously saved AMI by tag, using `<environment>_<tag>` instead of the default Ubuntu AMI.
- Add a deploy-time option to list available AMIs for an environment (`<environment>_*`) so users can choose an image to launch.
- Preserve existing default behavior when no AMI save/load/list option is provided.

## Capabilities

### New Capabilities

- `environment-ami-save-on-stop`: Save current instance state to an AMI with deterministic `<environment>_<tag>` naming before stack teardown.
- `environment-ami-select-on-deploy`: Support listing and selecting environment-scoped AMIs during deploy, and launching Spot capacity from the selected AMI.

### Modified Capabilities

- None.

## Impact

- Affected code paths include `make <environment>` deploy/stop orchestration and CDK deploy/destroy command wrappers.
- AWS interactions will expand to include AMI create/list/lookup operations (EC2 APIs) and related error handling.
- Deployment logic must conditionally bypass default bootstrap userData when launching from a saved AMI.
- User-facing documentation and CLI usage examples in `README.md` will need updates for new arguments and expected naming/tag conventions.
