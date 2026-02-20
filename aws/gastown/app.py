#!/usr/bin/env python3
import base64
import os
from pathlib import Path

import aws_cdk as cdk

from aws_workstation.aws_workstation_stack import AwsWorkstationStack

def get_account() -> str:
    acct = os.getenv("CDK_DEFAULT_ACCOUNT")
    if acct:
        return acct.strip()

    secret_path = Path("/run/secrets/aws_acct")
    if secret_path.exists():
        return secret_path.read_text(encoding="utf-8").strip()

    raise RuntimeError("No AWS account found in CDK_DEFAULT_ACCOUNT or /run/secrets/aws_acct")

user_data = {}
for filename in os.listdir("init"):
    path = os.path.join("init", filename)
    name = filename.split(".")[0]
    user_data = ""

app = cdk.App()
AwsWorkstationStack(app, "AwsWorkstationStack",
    user_data=user_data,
    # If you don't specify 'env', this stack will be environment-agnostic.
    # Account/Region-dependent features and context lookups will not work,
    # but a single synthesized template can be deployed anywhere.

    # Uncomment the next line to specialize this stack for the AWS Account
    # and Region that are implied by the current CLI configuration.

    #env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),

    # Uncomment the next line if you know exactly what Account and Region you
    # want to deploy the stack to. */

    env=cdk.Environment(
        account=os.environ["CDK_DEFAULT_ACCOUNT"],
        region=os.environ.get("CDK_DEFAULT_REGION", "us-west-2")
    ),

    # For more information, see https://docs.aws.amazon.com/cdk/latest/guide/environments.html
    )

app.synth()
