## 1. CLI and argument plumbing

- [ ] 1.1 Identify and document existing deploy/stop argument flow for `make <environment>` and map insertion points for `AMI_TAG`, `AMI_LOAD_TAG`, and `AMI_LIST`.
- [ ] 1.2 Add Make/orchestration argument parsing for AMI save-on-stop, AMI load-on-deploy, and AMI list mode while preserving current defaults when flags are absent.
- [ ] 1.3 Validate mutually exclusive/invalid combinations (for example, missing tag for save/load) and return actionable usage errors.

## 2. Stop flow: save AMI before destroy

- [ ] 2.1 Implement environment instance resolution for `ACTION=STOP` to identify the EC2 instance to snapshot.
- [ ] 2.2 Implement AMI creation with deterministic naming `<environment>_<tag>` when save mode is enabled.
- [ ] 2.3 Implement wait/poll logic for AMI state and fail with timeout/error details if image creation does not become usable.
- [ ] 2.4 Gate `cdk destroy` behind AMI save success so destroy is skipped when requested save fails.

## 3. Deploy flow: load or list environment AMIs

- [ ] 3.1 Implement AMI lookup by exact name `<environment>_<tag>` and pass resolved AMI ID into CDK deploy context/parameters.
- [ ] 3.2 Implement missing-AMI guardrail that aborts deploy before Spot request creation with a clear not-found message.
- [ ] 3.3 Implement AMI list mode that returns AMIs matching `<environment>_*`, ordered for user choice, including state visibility.
- [ ] 3.4 Implement list-and-pick deploy UX so users can choose an AMI from the displayed environment list and continue deploy in one flow.

## 4. Instance bootstrap behavior controls

- [ ] 4.1 Add deploy branching to use default Ubuntu AMI plus bootstrap when no AMI load option is provided.
- [ ] 4.2 Add deploy branching to launch from selected AMI and skip full bootstrap userData by default for restored environments.
- [ ] 4.3 Add/validate optional override behavior if minimal bootstrap-on-restored-AMI support is required by existing scripts.

## 5. Reliability, permissions, and observability

- [ ] 5.1 Add robust error handling and user-facing logs for EC2 AMI create/list/describe failures and timeouts.
- [ ] 5.2 Validate/update IAM permission requirements for AMI operations and surface early permission diagnostics.
- [ ] 5.3 Add tests for argument parsing and workflow branching (default deploy, save success/failure, load success/missing, list mode, list-and-pick path).

## 6. Documentation and rollout

- [ ] 6.1 Update `README.md` with concrete examples for save-on-stop, deploy-from-tag, and list/select AMI flows.
- [ ] 6.2 Document naming/tag conventions (`<environment>_<tag>`), expected AMI states, and failure behaviors for operators.
- [ ] 6.3 Add rollback notes describing how to disable AMI options and revert to legacy deploy/stop behavior.
