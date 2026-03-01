## ADDED Requirements

### Requirement: Deploy SHALL support loading AMI by environment tag
The deploy workflow SHALL accept a user-provided AMI tag and launch the environment using the AMI whose name matches `<environment>_<tag>`.

#### Scenario: Deploy from named AMI
- **WHEN** the user runs `make <environment>` with an AMI load tag argument
- **THEN** the system resolves an AMI named `<environment>_<tag>` and uses that AMI for the Spot launch

### Requirement: Deploy MUST fail when requested AMI does not exist
If a deploy request includes an AMI load tag and no matching AMI is found, the system MUST fail before infrastructure launch with an error that includes the expected AMI name.

#### Scenario: Missing requested AMI
- **WHEN** no AMI exists with the exact name `<environment>_<tag>` for the requested deploy
- **THEN** deployment stops before Spot request creation and returns a not-found error

### Requirement: Deploy SHALL list environment-scoped AMIs on request
The deploy workflow SHALL support a list mode that returns available AMIs whose names match `<environment>_*` so the user can choose one for subsequent deploy.

#### Scenario: List available environment AMIs
- **WHEN** the user runs `make <environment>` with AMI list mode enabled
- **THEN** the system outputs available AMIs matching `<environment>_*` with enough metadata for user selection

### Requirement: Default deploy behavior MUST remain unchanged without AMI options
When no AMI load or list option is provided, the deploy workflow MUST continue to use the default Ubuntu AMI and existing bootstrap path.

#### Scenario: Standard deploy without AMI options
- **WHEN** the user runs `make <environment>` with no AMI-related arguments
- **THEN** the system deploys from the default Ubuntu AMI and runs the existing bootstrap behavior

