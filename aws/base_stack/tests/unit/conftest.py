"""Pytest configuration for base_stack unit tests.

Stubs out bootstrap user-data generation so CDK stack tests do not require
``init/`` files to be present at the working directory.  The actual content
of bootstrap scripts is not under test here; stack tests focus on CDK
resource properties.
"""

import pytest
from unittest.mock import patch


@pytest.fixture(autouse=True)
def stub_bootstrap_user_data():
    """Replace build_bootstrap_user_data with a stable stub for all stack tests."""
    with patch(
        "workstation_core.cdk_helpers.build_bootstrap_user_data",
        return_value="c3R1Yi1ib290c3RyYXA=",  # base64("stub-bootstrap")
    ):
        yield
