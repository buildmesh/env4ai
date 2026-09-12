"""Tests for composing cloud-init keys and existing bootstrap user data."""

import base64
import json
from email import policy
from email.parser import BytesParser

import pytest

from workstation_core.cloud_init import add_ssh_authorized_keys


@pytest.mark.parametrize("bootstrap", [None, "IyEvYmluL2Jhc2gKZWNobyBoaQo="])
def test_empty_keys_preserve_original_user_data(bootstrap: str | None) -> None:
    """An omitted key list leaves both absent and existing data unchanged."""
    assert add_ssh_authorized_keys(bootstrap, ()) == bootstrap


def test_keys_only_cloud_config_preserves_strings() -> None:
    """Keys-only launches safely encode comments with YAML-sensitive characters."""
    keys = ['ssh-ed25519 AAAA user: "laptop" # café', "ssh-rsa AAAA second"]
    encoded = add_ssh_authorized_keys(None, keys)
    config = base64.b64decode(encoded).decode()
    assert config.startswith("#cloud-config\n")
    assert json.loads(config.split("\n", 1)[1]) == {"ssh_authorized_keys": keys}


def test_multipart_preserves_bootstrap_and_is_deterministic() -> None:
    """Cloud-init gets two correctly typed parts without changing shell content."""
    script = "#!/bin/bash\necho 'café'\n"
    bootstrap = base64.b64encode(script.encode()).decode()
    keys = ("ssh-ed25519 AAAA alice", "ssh-rsa AAAA bob")
    encoded = add_ssh_authorized_keys(bootstrap, keys)
    assert encoded == add_ssh_authorized_keys(bootstrap, keys)
    message = BytesParser(policy=policy.default).parsebytes(base64.b64decode(encoded))
    assert len(message.get_boundary()) <= 70
    assert not message.defects
    cloud_config, shell = list(message.iter_parts())
    assert cloud_config.get_content_type() == "text/cloud-config"
    assert json.loads(cloud_config.get_content().split("\n", 1)[1]) == {
        "ssh_authorized_keys": list(keys)
    }
    assert shell.get_content_type() == "text/x-shellscript"
    assert shell.get_content() == script


def test_invalid_bootstrap_encoding_is_rejected() -> None:
    """Malformed bootstrap must fail rather than silently lose its contents."""
    with pytest.raises(ValueError):
        add_ssh_authorized_keys("not base64!", ("ssh-ed25519 AAAA alice",))
