# SSM Access Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deploy-time `ACCESS_MODE=ssh|ssm|both` so environments can launch with SSH, SSM, or both, backed by shared SSM network infrastructure and a shared SSM EC2 instance role/profile.

**Architecture:** Keep the user’s access choice as deploy-time orchestration input, not as the primary environment definition. `Env4aiNetworkStack` always owns the reusable SSM infrastructure and IAM resources, while `WorkstationStack` consumes those shared resources conditionally based on the selected access mode. Post-deploy output and README examples must describe the selected connection method clearly.

**Tech Stack:** Python 3, AWS CDK, boto3, unittest, Make, OpenSpec-style documentation already present in repo

---

## File Structure

- Modify: `Makefile`
  - Export `ACCESS_MODE` into the containerized workflow so deploy/interactive flows can see it.
- Modify: `aws/workstation_core/environment_config.py`
  - Add an optional per-environment default access mode contract.
- Modify: `aws/workstation_core/cdk_helpers.py`
  - Add shared access-mode validation and Spot Fleet launch-spec support for optional key name, extra security groups, and instance profile.
- Modify: `aws/workstation_core/orchestration.py`
  - Resolve `ACCESS_MODE` from CLI/env/spec default and pass it into deploy + post-deploy flows.
- Modify: `aws/scripts/deploy_workstation.py`
  - Accept optional `--access-mode` to override env/default behavior.
- Modify: `aws/base_stack/app.py`
  - Parse access-mode CDK context and pass shared SSM resources into `WorkstationStack`.
- Modify: `aws/base_stack/workstation/env4ai_network_stack.py`
  - Create SSM endpoint subnet, interface endpoints, SSM SGs, EC2 role, and instance profile.
- Modify: `aws/base_stack/workstation/workstation_stack.py`
  - Conditionally attach SSH SG, SSM client SG, key pair, and instance profile based on `ACCESS_MODE`.
- Modify: `aws/scripts/check_instance.py`
  - Print SSH guidance, SSM guidance, or both depending on access mode.
- Modify: `aws/iam/deployer-policy.json`
  - Add IAM and EC2 permissions for instance profiles and VPC endpoints.
- Modify: `README.md`
  - Document `ACCESS_MODE`, SSM prerequisites, and example commands.
- Test: `aws/base_stack/tests/unit/test_env4ai_network_stack.py`
  - Verify shared SSM subnet, endpoints, SGs, role, and profile.
- Test: `aws/base_stack/tests/unit/test_workstation_stack.py`
  - Verify stack shape for `ssh`, `ssm`, and `both`.
- Test: `aws/base_stack/tests/unit/test_app.py`
  - Verify context parsing and shared-resource wiring.
- Test: `aws/base_stack/tests/unit/test_deploy_workstation.py`
  - Verify wrapper accepts and forwards `--access-mode`.
- Test: `aws/workstation_core/tests/unit/test_deploy_orchestration.py`
  - Verify access-mode resolution, deploy context, and post-deploy branching.
- Test: `aws/base_stack/tests/unit/test_check.py`
  - Verify user-facing connection instructions for each access mode.

### Task 1: Add Access Mode Contract And CLI Plumbing

**Files:**
- Modify: `Makefile`
- Modify: `aws/workstation_core/environment_config.py`
- Modify: `aws/scripts/deploy_workstation.py`
- Modify: `aws/workstation_core/orchestration.py`
- Test: `aws/base_stack/tests/unit/test_deploy_workstation.py`
- Test: `aws/workstation_core/tests/unit/test_deploy_orchestration.py`

- [ ] **Step 1: Write the failing CLI wrapper test**

```python
def test_parse_args_accepts_optional_access_mode(self) -> None:
    args = parse_args(
        [
            "--environment",
            "test",
            "--stack-dir",
            "/tmp/test",
            "--stack-name",
            "TestWorkstationStack",
            "--access-mode",
            "ssm",
        ]
    )

    self.assertEqual("ssm", args.access_mode)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd aws/gastown && uv run python -m unittest ../base_stack/tests/unit/test_deploy_workstation.py -v`
Expected: FAIL because `deploy_workstation.parse_args()` does not define `--access-mode`

- [ ] **Step 3: Write the minimal CLI implementation**

```python
parser.add_argument(
    "--access-mode",
    choices=("ssh", "ssm", "both"),
    default=None,
    help="Optional workstation access mode override.",
)

return run_deploy_lifecycle(
    DeployWorkflowInputs(
        environment=args.environment,
        stack_dir=args.stack_dir,
        stack_name=args.stack_name,
        profile=args.profile,
        region=args.region,
        access_mode=args.access_mode,
    )
)
```

- [ ] **Step 4: Add the deploy-workflow contract and default resolver**

```python
@dataclass(frozen=True, slots=True)
class DeployWorkflowInputs:
    environment: str
    stack_dir: str
    stack_name: str
    profile: str | None = None
    region: str | None = None
    access_mode: str | None = None


def resolve_access_mode(
    *,
    cli_access_mode: str | None,
    env: Mapping[str, str],
    environment_spec: object | None,
) -> str:
    if cli_access_mode and cli_access_mode.strip():
        return cli_access_mode.strip()
    if env.get("ACCESS_MODE", "").strip():
        return env["ACCESS_MODE"].strip()
    default_access_mode = getattr(environment_spec, "default_access_mode", "ssh")
    return str(default_access_mode).strip() or "ssh"
```

- [ ] **Step 5: Add the optional environment-spec default**

```python
@dataclass(frozen=True, slots=True)
class EnvironmentSpec:
    environment_key: str
    display_name: str
    bootstrap_files: tuple[str, ...]
    default_ami_selector: AmiSelectorConfig
    subnet_cidr: str
    instance_type: str
    volume_size: int
    spot_price: str
    default_access_mode: str = "ssh"
```

- [ ] **Step 6: Export the new deploy-time variable from Make**

```make
DOCKER_COMPOSE_RUN := docker compose run --rm \
	-e AWS_PROFILE \
	-e AWS_REGION \
	-e AWS_DEFAULT_REGION \
	-e CDK_DEFAULT_REGION \
	-e CDK_DEFAULT_ACCOUNT \
	-e ACCESS_MODE \
	-e AMI_LOAD \
	-e AMI_LIST \
	-e AMI_PICK \
	-e AMI_BOOTSTRAP \
	-e AMI_SAVE \
	-e AMI_TAG \
	-e EIP_DESTROY
```

- [ ] **Step 7: Add orchestration tests for explicit and default access mode**

```python
def test_run_deploy_lifecycle_prefers_cli_access_mode(self) -> None:
    env = {"AWS_REGION": "us-west-2", "ACCESS_MODE": "ssh"}
    selection = Mock(should_deploy=True, selected_ami_id=None)

    with (
        patch("workstation_core.orchestration.load_environment_spec", return_value=Mock(default_access_mode="both")),
        patch("workstation_core.orchestration.make_ec2_client", return_value=Mock()),
        patch("workstation_core.orchestration.resolve_ami_selection", return_value=selection),
        patch("workstation_core.orchestration.find_or_create_eip", return_value={"allocation_id": "eipalloc-1", "public_ip": "1.2.3.4"}),
        patch("workstation_core.orchestration.deploy_shared_network_stack"),
        patch("workstation_core.orchestration.deploy_stack") as deploy_stack,
        patch("workstation_core.orchestration.run_post_deploy_check"),
    ):
        run_deploy_lifecycle(
            inputs=DeployWorkflowInputs(
                environment="gastown",
                stack_dir="/tmp/gastown",
                stack_name="GastownWorkstationStack",
                access_mode="ssm",
            ),
            env=env,
            out=io.StringIO(),
        )

    deploy_stack.assert_called_once()
    self.assertEqual("ssm", deploy_stack.call_args.kwargs["access_mode"])
```

- [ ] **Step 8: Run focused tests to verify they pass**

Run: `cd aws/gastown && uv run python -m unittest ../base_stack/tests/unit/test_deploy_workstation.py ../workstation_core/tests/unit/test_deploy_orchestration.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add Makefile aws/workstation_core/environment_config.py aws/scripts/deploy_workstation.py aws/workstation_core/orchestration.py aws/base_stack/tests/unit/test_deploy_workstation.py aws/workstation_core/tests/unit/test_deploy_orchestration.py
git commit -m "feat: add deploy-time access mode plumbing"
```

### Task 2: Build Shared SSM Infrastructure In Env4aiNetworkStack

**Files:**
- Modify: `aws/base_stack/workstation/env4ai_network_stack.py`
- Modify: `aws/iam/deployer-policy.json`
- Test: `aws/base_stack/tests/unit/test_env4ai_network_stack.py`

- [ ] **Step 1: Write the failing shared-network test for SSM resources**

```python
def test_network_stack_creates_shared_ssm_infrastructure(self) -> None:
    app = core.App()
    stack = Env4aiNetworkStack(app, "Env4aiNetworkStack", env=self._test_env())
    template = assertions.Template.from_stack(stack)

    template.resource_count_is("AWS::EC2::VPCEndpoint", 3)
    template.resource_count_is("AWS::IAM::Role", 1)
    template.resource_count_is("AWS::IAM::InstanceProfile", 1)
    template.has_resource_properties(
        "AWS::IAM::Role",
        {
            "ManagedPolicyArns": assertions.Match.array_with(
                [
                    {
                        "Fn::Join": assertions.Match.any_value(),
                    }
                ]
            )
        },
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd aws/gastown && uv run python -m unittest ../base_stack/tests/unit/test_env4ai_network_stack.py -v`
Expected: FAIL because the stack currently creates only VPC and Internet Gateway

- [ ] **Step 3: Add shared SSM subnet, SGs, role, and profile**

```python
self.ssm_endpoint_subnet = ec2.PrivateSubnet(
    self,
    "SsmEndpointsSubnet",
    availability_zone=ec2.Fn.select(0, ec2.Fn.get_azs()),
    cidr_block="10.0.250.0/24",
    vpc_id=self.vpc.vpc_id,
)

self.ssm_endpoints_sg = ec2.SecurityGroup(
    self,
    "SsmEndpointsSecurityGroup",
    vpc=self.vpc,
    allow_all_outbound=True,
)
self.ssm_clients_sg = ec2.SecurityGroup(
    self,
    "SsmClientsSecurityGroup",
    vpc=self.vpc,
    allow_all_outbound=False,
)
self.ssm_clients_sg.add_egress_rule(self.ssm_endpoints_sg, ec2.Port.tcp(443), "Allow HTTPS to SSM endpoints")
self.ssm_endpoints_sg.add_ingress_rule(self.ssm_clients_sg, ec2.Port.tcp(443), "Allow SSM clients")

self.ssm_instance_role = iam.Role(
    self,
    "SsmEc2InstanceRole",
    assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
    managed_policies=[
        iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore"),
    ],
)
self.ssm_instance_profile = iam.CfnInstanceProfile(
    self,
    "SsmEc2InstanceProfile",
    roles=[self.ssm_instance_role.role_name],
)
```

- [ ] **Step 4: Add interface endpoints and optional `ec2messages` handling**

```python
for service_name in ("ssm", "ssmmessages"):
    ec2.InterfaceVpcEndpoint(
        self,
        f"{service_name.title()}Endpoint",
        vpc=self.vpc,
        service=ec2.InterfaceVpcEndpointAwsService(service_name),
        subnets=ec2.SubnetSelection(subnets=[self.ssm_endpoint_subnet]),
        security_groups=[self.ssm_endpoints_sg],
        private_dns_enabled=True,
    )

try:
    ec2.InterfaceVpcEndpoint(
        self,
        "Ec2MessagesEndpoint",
        vpc=self.vpc,
        service=ec2.InterfaceVpcEndpointAwsService("ec2messages"),
        subnets=ec2.SubnetSelection(subnets=[self.ssm_endpoint_subnet]),
        security_groups=[self.ssm_endpoints_sg],
        private_dns_enabled=True,
    )
except Exception:
    Annotations.of(self).add_warning(
        "Skipping ec2messages endpoint because this region does not support it."
    )
```

- [ ] **Step 5: Add the deployer-policy permissions**

```json
{
  "Sid": "EC2VpcEndpoints",
  "Effect": "Allow",
  "Action": [
    "ec2:CreateVpcEndpoint",
    "ec2:DeleteVpcEndpoints",
    "ec2:DescribeVpcEndpoints",
    "ec2:ModifyVpcEndpoint"
  ],
  "Resource": "*"
},
{
  "Sid": "IamInstanceProfilesForSsm",
  "Effect": "Allow",
  "Action": [
    "iam:CreateRole",
    "iam:DeleteRole",
    "iam:CreateInstanceProfile",
    "iam:DeleteInstanceProfile",
    "iam:AddRoleToInstanceProfile",
    "iam:RemoveRoleFromInstanceProfile",
    "iam:AttachRolePolicy",
    "iam:DetachRolePolicy",
    "iam:GetRole",
    "iam:GetInstanceProfile",
    "iam:PassRole"
  ],
  "Resource": "*"
}
```

- [ ] **Step 6: Run focused tests to verify they pass**

Run: `cd aws/gastown && uv run python -m unittest ../base_stack/tests/unit/test_env4ai_network_stack.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add aws/base_stack/workstation/env4ai_network_stack.py aws/iam/deployer-policy.json aws/base_stack/tests/unit/test_env4ai_network_stack.py
git commit -m "feat: add shared ssm network resources"
```

### Task 3: Make WorkstationStack Consume Shared Access Resources

**Files:**
- Modify: `aws/workstation_core/cdk_helpers.py`
- Modify: `aws/base_stack/workstation/workstation_stack.py`
- Test: `aws/base_stack/tests/unit/test_workstation_stack.py`

- [ ] **Step 1: Write the failing workstation-stack tests for `ssm` and `both`**

```python
def test_ssm_mode_omits_ssh_ingress_and_key_name(self) -> None:
    app = core.App()
    stack = self._make_stack(app, "aws-workstation-ssm-only", access_mode="ssm")
    template = assertions.Template.from_stack(stack)
    template_json = template.to_json()

    self.assertEqual(0, len(template.find_resources("AWS::EC2::SecurityGroupIngress")))
    launch_spec = template_json["Resources"]["TestSpotFleet"]["Properties"]["SpotFleetRequestConfigData"]["LaunchSpecifications"][0]
    self.assertNotIn("KeyName", launch_spec)

def test_both_mode_keeps_ssh_and_attaches_instance_profile(self) -> None:
    app = core.App()
    stack = self._make_stack(app, "aws-workstation-both", access_mode="both")
    template = assertions.Template.from_stack(stack)
    template.has_resource_properties("AWS::EC2::SecurityGroupIngress", {"FromPort": 22, "ToPort": 22})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd aws/gastown && uv run python -m unittest ../base_stack/tests/unit/test_workstation_stack.py -v`
Expected: FAIL because `WorkstationStack` currently always adds SSH ingress and always sets `key_name`

- [ ] **Step 3: Add launch-spec helper support for optional key name, extra SGs, and instance profile**

```python
def build_spot_fleet_launch_specification(
    *,
    ami_id: str,
    instance_type: str,
    security_group_ids: list[str],
    subnet_id: str,
    volume_size: int,
    include_bootstrap_user_data: bool,
    bootstrap_files: tuple[str, ...],
    key_name: str | None,
    iam_instance_profile_arn: str | None = None,
    verbose_bootstrap_resolution: bool = False,
) -> dict[str, object]:
    launch_specification: dict[str, object] = {
        "image_id": ami_id,
        "instance_type": instance_type,
        "security_groups": [{"groupId": group_id} for group_id in security_group_ids],
        "subnet_id": subnet_id,
        "block_device_mappings": [...],
    }
    if key_name:
        launch_specification["key_name"] = key_name
    if iam_instance_profile_arn:
        launch_specification["iam_instance_profile"] = {"arn": iam_instance_profile_arn}
    return launch_specification
```

- [ ] **Step 4: Add access-mode conditional wiring in the workstation stack**

```python
ssh_sg = ec2.SecurityGroup(self, environment_spec.construct_id("SshSecurityGroup"), vpc=shared_vpc)
if access_mode in {"ssh", "both"}:
    ssh_sg.add_ingress_rule(ec2.Peer.any_ipv4(), ec2.Port.tcp(22), "Allow SSH")

security_group_ids: list[str] = []
if access_mode in {"ssh", "both"}:
    security_group_ids.append(ssh_sg.security_group_id)
if access_mode in {"ssm", "both"}:
    security_group_ids.append(shared_ssm_clients_security_group_id)

launch_specification = build_spot_fleet_launch_specification(
    ami_id=ami_id,
    instance_type=environment_spec.instance_type,
    security_group_ids=security_group_ids,
    subnet_id=local_zone_subnet.ref,
    volume_size=environment_spec.volume_size,
    include_bootstrap_user_data=should_include_bootstrap,
    bootstrap_files=environment_spec.bootstrap_files,
    key_name="aws_key" if access_mode in {"ssh", "both"} else None,
    iam_instance_profile_arn=shared_ssm_instance_profile_arn if access_mode in {"ssm", "both"} else None,
    verbose_bootstrap_resolution=verbose_bootstrap_resolution,
)
```

- [ ] **Step 5: Run focused tests to verify they pass**

Run: `cd aws/gastown && uv run python -m unittest ../base_stack/tests/unit/test_workstation_stack.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add aws/workstation_core/cdk_helpers.py aws/base_stack/workstation/workstation_stack.py aws/base_stack/tests/unit/test_workstation_stack.py
git commit -m "feat: add workstation ssh and ssm access modes"
```

### Task 4: Wire CDK Context Through app.py And Improve Connection Output

**Files:**
- Modify: `aws/base_stack/app.py`
- Modify: `aws/scripts/check_instance.py`
- Test: `aws/base_stack/tests/unit/test_app.py`
- Test: `aws/base_stack/tests/unit/test_check.py`

- [ ] **Step 1: Write the failing app/context and output tests**

```python
def test_main_passes_access_mode_and_shared_ssm_resources(self) -> None:
    app_instance = Mock()
    app_instance.node.try_get_context.side_effect = (
        lambda key: "ssm" if key == "access_mode" else None
    )
    network_stack = Mock(
        vpc="vpc",
        internet_gateway=Mock(ref="igw"),
        ssm_clients_sg=Mock(security_group_id="sg-ssm"),
        ssm_instance_profile=Mock(attr_arn="arn:aws:iam::111111111111:instance-profile/ssm"),
    )

    with (
        patch("app.cdk.App", return_value=app_instance),
        patch("app.cdk.Environment", return_value=Mock()),
        patch("app.get_account", return_value="111111111111"),
        patch("app.get_region", return_value="us-west-2"),
        patch("app.Env4aiNetworkStack", return_value=network_stack),
        patch("app.WorkstationStack") as stack_mock,
    ):
        base_app.main()

    self.assertEqual("ssm", stack_mock.call_args.kwargs["access_mode"])
```

```python
def test_main_prints_ssm_command_when_access_mode_is_ssm(self) -> None:
    args = type(
        "Args",
        (),
        {
            "region": "us-west-2",
            "profile": None,
            "stack_name": "TestWorkstationStack",
            "spot_fleet_logical_id": "TestSpotFleet",
            "ssh_host_alias": "test-workstation",
            "ssh_user": "ubuntu",
            "identity_file": "~/.ssh/aws_key.pem",
            "eip_allocation_id": None,
            "eip_public_ip": None,
            "access_mode": "ssm",
        },
    )()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd aws/gastown && uv run python -m unittest ../base_stack/tests/unit/test_app.py ../base_stack/tests/unit/test_check.py -v`
Expected: FAIL because `access_mode` is not parsed or printed yet

- [ ] **Step 3: Parse CDK context and pass the shared resource identifiers**

```python
access_mode_context = app.node.try_get_context("access_mode")
access_mode = "ssh"
if access_mode_context is not None:
    access_mode = parse_access_mode_context(access_mode_context)

workstation_stack = WorkstationStack(
    app,
    ENVIRONMENT_SPEC.stack_name,
    shared_vpc=network_stack.vpc,
    shared_igw_id=network_stack.internet_gateway.ref,
    shared_ssm_clients_security_group_id=network_stack.ssm_clients_sg.security_group_id,
    shared_ssm_instance_profile_arn=network_stack.ssm_instance_profile.attr_arn,
    access_mode=access_mode,
    ...
)
```

- [ ] **Step 4: Update `check_instance.py` to print mode-specific guidance**

```python
def build_ssm_start_session_command(region: str, instance_id: str, profile: str | None) -> str:
    profile_segment = f" --profile {profile}" if profile else ""
    return f"aws ssm start-session --region {region}{profile_segment} --target {instance_id}"

if args.access_mode in {"ssm", "both"}:
    print("\nStart an SSM session:\n")
    print(build_ssm_start_session_command(region=region, instance_id=instance_id, profile=normalize_optional(args.profile)))

if args.access_mode in {"ssh", "both"}:
    print(f"Public IP: {display_ip}")
    print("\nAdd this to ~/.ssh/config:\n")
    print(build_ssh_config_snippet(...))
```

- [ ] **Step 5: Run focused tests to verify they pass**

Run: `cd aws/gastown && uv run python -m unittest ../base_stack/tests/unit/test_app.py ../base_stack/tests/unit/test_check.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add aws/base_stack/app.py aws/scripts/check_instance.py aws/base_stack/tests/unit/test_app.py aws/base_stack/tests/unit/test_check.py
git commit -m "feat: add access mode context and connection guidance"
```

### Task 5: Document And Verify The End-To-End Feature

**Files:**
- Modify: `README.md`
- Modify: `aws/launcher/environment_config.py`
- Modify: `aws/gastown/environment_config.py`
- Modify: `aws/builder/environment_config.py`
- Test: existing unit suites touched above

- [ ] **Step 1: Update environment specs to make the default explicit**

```python
_ENVIRONMENT_SPEC = EnvironmentSpec(
    environment_key="gastown",
    display_name="Gastown",
    bootstrap_files=(...),
    default_ami_selector=AmiSelectorConfig(...),
    subnet_cidr="10.0.1.0/24",
    instance_type="t3.medium",
    volume_size=16,
    spot_price="0.1",
    default_access_mode="ssh",
)
```

- [ ] **Step 2: Update the README with `ACCESS_MODE` behavior and examples**

```md
### Access modes

Use `ACCESS_MODE` to choose how a workstation is reached:

- `ACCESS_MODE=ssh` - existing behavior, SSH ingress from the internet and EC2 key pair
- `ACCESS_MODE=ssm` - no inbound SSH, instance profile + SSM client SG, connect with Session Manager
- `ACCESS_MODE=both` - keep SSH and enable SSM at the same time

Examples:

```bash
make gastown ACCESS_MODE=ssh
make gastown ACCESS_MODE=ssm
make gastown ACCESS_MODE=both
```

For `ACCESS_MODE=ssm` or `ACCESS_MODE=both`, install the AWS Session Manager plugin on the machine where you will run `aws ssm start-session`.
```

- [ ] **Step 3: Run the full relevant test suite**

Run: `cd aws/gastown && uv run python -m unittest ../base_stack/tests/unit/test_env4ai_network_stack.py ../base_stack/tests/unit/test_workstation_stack.py ../base_stack/tests/unit/test_app.py ../base_stack/tests/unit/test_deploy_workstation.py ../base_stack/tests/unit/test_check.py ../workstation_core/tests/unit/test_deploy_orchestration.py -v`
Expected: PASS

- [ ] **Step 4: Review synthesized behavior manually**

Run: `cd aws/gastown && ACCESS_MODE=ssm uv run cdk synth`
Expected: synthesized Spot Fleet launch spec has no `KeyName`, workstation launch spec includes IAM instance profile, and shared stack includes SSM endpoints + instance profile resources

- [ ] **Step 5: Commit**

```bash
git add README.md aws/launcher/environment_config.py aws/gastown/environment_config.py aws/builder/environment_config.py
git commit -m "docs: describe ssh and ssm access modes"
```

## Self-Review

### Spec coverage

- Shared SSM infrastructure in `Env4aiNetworkStack`: covered by Task 2.
- Shared SSM EC2 role + instance profile: covered by Task 2.
- Deploy-time `ACCESS_MODE=ssh|ssm|both`: covered by Tasks 1, 3, and 4.
- `ssm` mode removes SSH ingress and avoids key management: covered by Task 3.
- `both` mode preserves SSH while enabling SSM: covered by Task 3.
- Post-deploy instructions for SSM/SSH: covered by Task 4.
- README/operator guidance: covered by Task 5.
- IAM/deployer permission updates: covered by Task 2.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” markers remain.
- Every code-changing step includes a concrete code block.
- Every verification step includes an explicit command and expected outcome.

### Type consistency

- `access_mode` is used consistently across CLI, orchestration, CDK context, stack wiring, and output helpers.
- The shared stack exposes `ssm_clients_sg` and `ssm_instance_profile`, and the workstation stack consumes `shared_ssm_clients_security_group_id` and `shared_ssm_instance_profile_arn`.
- The deploy-time values remain `ssh`, `ssm`, and `both` everywhere in the plan.
