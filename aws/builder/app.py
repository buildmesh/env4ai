#!/usr/bin/env python3
import configparser
import os
from pathlib import Path
from typing import Mapping

import aws_cdk as cdk

from builder_workstation.builder_workstation_stack import BuilderWorkstationStack

def get_profile_name(env: Mapping[str, str] | None = None) -> str:
    """Return the active AWS profile name.

    Args:
        env: Optional environment mapping for testability.

    Returns:
        The trimmed profile name, or ``default`` if unset.
    """
    source = env if env is not None else os.environ
    profile_name = source.get("AWS_PROFILE", "").strip()
    return profile_name or "default"


def get_profile_section_name(profile_name: str) -> str:
    """Map a profile name to the corresponding ~/.aws/config section name.

    Args:
        profile_name: The active profile name.

    Returns:
        The INI section name for the profile.
    """
    if profile_name == "default":
        return "default"
    return f"profile {profile_name}"


def load_aws_config(config_path: Path | None = None) -> configparser.ConfigParser:
    """Load AWS CLI config from disk.

    Args:
        config_path: Optional file path for testability.

    Returns:
        Parsed ``ConfigParser`` instance.

    Raises:
        RuntimeError: If the config file is missing.
    """
    path = config_path or (Path.home() / ".aws" / "config")
    if not path.exists():
        raise RuntimeError(
            "Unable to resolve AWS region: ~/.aws/config was not found and CDK_DEFAULT_REGION is not set."
        )

    config = configparser.ConfigParser()
    config.read(path, encoding="utf-8")
    return config


def get_region_from_config(config: configparser.ConfigParser, profile_name: str) -> str:
    """Resolve an AWS region value from a loaded AWS config.

    Args:
        config: Parsed AWS config.
        profile_name: Active profile name.

    Returns:
        Trimmed AWS region string.

    Raises:
        RuntimeError: If the profile section or region value is missing.
    """
    section_name = get_profile_section_name(profile_name)
    if not config.has_section(section_name):
        raise RuntimeError(
            f"Unable to resolve AWS region: profile section '[{section_name}]' was not found in ~/.aws/config."
        )

    region = config.get(section_name, "region", fallback="").strip()
    if not region:
        raise RuntimeError(
            f"Unable to resolve AWS region: no 'region' value found in profile '[{profile_name}]' in ~/.aws/config."
        )
    return region


def get_region(
    env: Mapping[str, str] | None = None, config_path: Path | None = None
) -> str:
    """Resolve AWS region based on environment and AWS config precedence.

    Args:
        env: Optional environment mapping for testability.
        config_path: Optional ~/.aws/config path for testability.

    Returns:
        Resolved AWS region.
    """
    source = env if env is not None else os.environ
    region = source.get("CDK_DEFAULT_REGION", "").strip()
    if region:
        return region

    profile_name = get_profile_name(source)
    config = load_aws_config(config_path=config_path)
    return get_region_from_config(config=config, profile_name=profile_name)


def get_account(
    env: Mapping[str, str] | None = None, secret_path: Path | None = None
) -> str:
    """Resolve AWS account based on environment and secret precedence.

    Args:
        env: Optional environment mapping for testability.
        secret_path: Optional account secret path for testability.

    Returns:
        Resolved AWS account ID.

    Raises:
        RuntimeError: If account cannot be resolved.
    """
    source = env if env is not None else os.environ
    account = source.get("CDK_DEFAULT_ACCOUNT", "").strip()
    if account:
        return account

    path = secret_path or Path("/run/secrets/aws_acct")
    if path.exists():
        account = path.read_text(encoding="utf-8").strip()
        if account:
            return account

    raise RuntimeError(
        "Unable to resolve AWS account: CDK_DEFAULT_ACCOUNT is not set and /run/secrets/aws_acct is missing or empty."
    )


def main() -> None:
    """Synthesize the CDK app for this environment."""
    app = cdk.App()
    BuilderWorkstationStack(
        app,
        "BuilderWorkstationStack",
        env=cdk.Environment(account=get_account(), region=get_region()),
    )
    app.synth()


if __name__ == "__main__":
    main()
