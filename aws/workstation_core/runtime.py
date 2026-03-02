"""Runtime metadata for workstation orchestration flows."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    """Runtime context shared by deployment orchestration.

    Args:
        account_id: AWS account identifier used for deployment.
        profile_name: Active AWS CLI profile name.
        dry_run: Whether operations should be run in no-op mode.
    """

    account_id: str
    profile_name: str
    dry_run: bool = False


def describe_runtime(context: RuntimeContext) -> str:
    """Return a stable summary string for logs and traces.

    Args:
        context: Runtime context to summarize.

    Returns:
        A single-line summary intended for diagnostics.
    """
    run_mode = "dry-run" if context.dry_run else "apply"
    return f"account={context.account_id} profile={context.profile_name} mode={run_mode}"
