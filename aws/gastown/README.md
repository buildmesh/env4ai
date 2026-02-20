
# Welcome to your CDK Python project!

This is a blank project for CDK development with Python.

The `cdk.json` file tells the CDK Toolkit how to execute your app.

This project uses `uv` to manage Python dependencies and run CDK commands.

Install or update project dependencies:

```
$ uv sync
```

Run CDK commands through `uv`:

```
$ uv run cdk synth
```

To add dependencies, update `pyproject.toml` and run:

```
$ uv lock
$ uv sync
```

## Useful commands

 * `uv run cdk ls`          list all stacks in the app
 * `uv run cdk synth`       emits the synthesized CloudFormation template
 * `uv run cdk deploy`      deploy this stack to your default AWS account/region
 * `uv run cdk diff`        compare deployed stack with current state
 * `uv run cdk docs`        open CDK documentation
 * `uv run python check.py` print the newest Spot Fleet instance IP and SSH config snippet

## Post-deploy SSH helper

After `cdk deploy`, run:

```
uv run python check.py --stack-name AwsWorkstationStack --region us-west-2
```

The script resolves the stack Spot Fleet resource, selects the newest instance, and prints a `~/.ssh/config` snippet.
Optional flags:

* `--profile sam`
* `--ssh-host-alias gastown-workstation`
* `--identity-file ~/.ssh/aws_key.pem`

Enjoy!
