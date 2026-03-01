## ADDED Requirements

### Requirement: Save AMI before stack destroy when explicitly requested
When a user stops an environment with AMI save enabled, the system SHALL create an EC2 AMI from the currently running environment instance before destroying the stack.

#### Scenario: Save enabled on stop
- **WHEN** the user runs `make <environment> ACTION=STOP` with an AMI save tag argument
- **THEN** the system creates an AMI from the environment instance before invoking `cdk destroy`

### Requirement: AMI name MUST follow environment tag convention
The AMI created during stop SHALL be named exactly `<environment>_<tag>` using the environment target name and user-provided tag value.

#### Scenario: Deterministic AMI naming
- **WHEN** the user requests save on stop for environment `gastown` with tag `20260228`
- **THEN** the AMI name is `gastown_20260228`

### Requirement: Destroy MUST be blocked on save failure
If AMI creation is requested and the create operation fails or does not become available in time, the system MUST abort stack destroy and return a clear actionable error.

#### Scenario: Save fails before destroy
- **WHEN** AMI creation returns an error or times out
- **THEN** `cdk destroy` is not executed and the user receives failure details

