"""Compose cloud-init SSH configuration with optional workstation bootstrap."""

import base64
import hashlib
import json
from collections.abc import Sequence
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def add_ssh_authorized_keys(
    bootstrap_user_data: str | None,
    ssh_authorized_keys: Sequence[str],
) -> str | None:
    """Add default-user SSH keys to base64-encoded EC2 user data.

    Args:
        bootstrap_user_data: Optional existing base64-encoded bootstrap script.
        ssh_authorized_keys: Public keys to add alongside existing authorized keys.

    Returns:
        Base64-encoded cloud-config or multipart data, or the original data when
        no keys are configured. Cloud-config alone also works on restored AMIs.
    """
    if not ssh_authorized_keys:
        return bootstrap_user_data

    cloud_config = (
        "#cloud-config\n"
        + json.dumps(
            {"ssh_authorized_keys": list(ssh_authorized_keys)}, ensure_ascii=True
        )
        + "\n"
    )
    if bootstrap_user_data is None:
        return base64.b64encode(cloud_config.encode("utf-8")).decode("ascii")

    script = base64.b64decode(bootstrap_user_data, validate=True).decode("utf-8")
    # Reason: a content-derived boundary keeps repeated CDK synthesis deterministic.
    boundary = (
        "env4ai-"
        + hashlib.sha256((cloud_config + script).encode("utf-8")).hexdigest()[:48]
    )
    message = MIMEMultipart(boundary=boundary)
    message.attach(MIMEText(cloud_config, "cloud-config"))
    message.attach(MIMEText(script, "x-shellscript"))
    return base64.b64encode(message.as_bytes()).decode("ascii")
