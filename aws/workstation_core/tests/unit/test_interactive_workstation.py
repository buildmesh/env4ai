"""Unit tests for interactive workstation helper flows."""

from __future__ import annotations

import io
from pathlib import Path
import tempfile
import unittest

from workstation_core.interactive_workstation import (
    EnvironmentTarget,
    choose_environment,
    discover_environments,
    dispatch_action,
    parse_action_choice,
)


class InteractiveWorkstationHelpersTests(unittest.TestCase):
    """Validate interactive discovery, picker, and action dispatch behavior."""

    @staticmethod
    def _write_environment_config(
        directory: Path,
        *,
        environment_key: str = "gastown",
        display_name: str = "Gastown",
    ) -> None:
        """Write a minimal valid ``environment_config.py`` for tests."""
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "environment_config.py").write_text(
            (
                "class _Spec:\n"
                "    environment_key = {!r}\n"
                "    display_name = {!r}\n"
                "    stack_name = {!r}\n"
                "    spot_fleet_logical_id = {!r}\n"
                "    ssh_alias = {!r}\n\n"
                "ENVIRONMENT_SPEC = _Spec()\n"
            ).format(
                environment_key,
                display_name,
                f"{display_name}WorkstationStack",
                f"{display_name}SpotFleet",
                f"{environment_key}-workstation",
            ),
            encoding="utf-8",
        )

    def test_discover_environments_loads_valid_environment_modules(self) -> None:
        """Expected: discovery returns valid environment targets."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            aws_root = Path(tmp_dir)
            self._write_environment_config(aws_root / "gastown", environment_key="gastown")
            self._write_environment_config(aws_root / "builder", environment_key="builder", display_name="Builder")
            output = io.StringIO()

            discovered = discover_environments(aws_root, output)

        self.assertEqual(["builder", "gastown"], [item.environment_key for item in discovered])
        self.assertEqual("", output.getvalue())

    def test_discover_environments_skips_malformed_candidates_with_warning(self) -> None:
        """Edge: malformed environment module is skipped without aborting discovery."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            aws_root = Path(tmp_dir)
            self._write_environment_config(aws_root / "gastown", environment_key="gastown")
            bad_dir = aws_root / "broken"
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "environment_config.py").write_text("ENVIRONMENT_SPEC = object()\n", encoding="utf-8")
            output = io.StringIO()

            discovered = discover_environments(aws_root, output)

        self.assertEqual(["gastown"], [item.environment_key for item in discovered])
        self.assertIn("Warning: skipping 'broken'", output.getvalue())

    def test_discover_environments_raises_when_no_valid_modules_found(self) -> None:
        """Failure: discovery fails fast with actionable guidance when no environments are valid."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            aws_root = Path(tmp_dir)
            output = io.StringIO()
            with self.assertRaisesRegex(RuntimeError, "No valid environments discovered under"):
                discover_environments(aws_root, output)

    @staticmethod
    def _targets() -> list[EnvironmentTarget]:
        """Return deterministic environment targets for picker/dispatch tests."""
        return [
            EnvironmentTarget(
                environment_key="gastown",
                display_name="Gastown",
                stack_dir=Path("/tmp/gastown"),
                stack_name="GastownWorkstationStack",
                spot_fleet_logical_id="GastownSpotFleet",
                ssh_alias="gastown-workstation",
            ),
            EnvironmentTarget(
                environment_key="builder",
                display_name="Builder",
                stack_dir=Path("/tmp/builder"),
                stack_name="BuilderWorkstationStack",
                spot_fleet_logical_id="BuilderSpotFleet",
                ssh_alias="builder-workstation",
            ),
        ]

    def test_choose_environment_accepts_numeric_selection(self) -> None:
        """Expected: numeric picker selection resolves the corresponding target."""
        output = io.StringIO()
        inputs = iter(["2"])
        selected = choose_environment(
            self._targets(),
            input_func=lambda _: next(inputs),
            out=output,
            last_used_environment_key=None,
        )
        self.assertIsNotNone(selected)
        self.assertEqual("builder", selected.environment_key)

    def test_choose_environment_uses_last_used_on_empty_input(self) -> None:
        """Edge: empty input selects last-used environment when available."""
        output = io.StringIO()
        inputs = iter([""])
        selected = choose_environment(
            self._targets(),
            input_func=lambda _: next(inputs),
            out=output,
            last_used_environment_key="gastown",
        )
        self.assertIsNotNone(selected)
        self.assertEqual("gastown", selected.environment_key)

    def test_choose_environment_retries_after_invalid_input(self) -> None:
        """Failure: invalid input retries with clear guidance."""
        output = io.StringIO()
        inputs = iter(["nope", "1"])
        selected = choose_environment(
            self._targets(),
            input_func=lambda _: next(inputs),
            out=output,
            last_used_environment_key=None,
        )
        self.assertIsNotNone(selected)
        self.assertEqual("gastown", selected.environment_key)
        self.assertIn("Unrecognized environment 'nope'", output.getvalue())

    def test_dispatch_action_runs_default_deploy_command(self) -> None:
        """Expected: deploy-default dispatches deploy script without AMI env overrides."""
        calls: list[tuple[list[str], Path, dict[str, str] | None]] = []
        environment = self._targets()[0]

        result = dispatch_action(
            "deploy_default",
            environment,
            input_func=lambda _: "",
            out=io.StringIO(),
            runner=lambda command, cwd, env_overrides: calls.append((command, cwd, env_overrides)),
        )

        self.assertFalse(result.switch_environment)
        self.assertFalse(result.should_quit)
        self.assertEqual(1, len(calls))
        self.assertEqual(None, calls[0][2])
        self.assertIn("../scripts/deploy_workstation.py", calls[0][0])

    def test_dispatch_action_switch_environment_returns_switch_signal(self) -> None:
        """Edge: switch action returns control to environment picker without commands."""
        environment = self._targets()[0]
        calls: list[tuple[list[str], Path, dict[str, str] | None]] = []
        result = dispatch_action(
            "switch_environment",
            environment,
            input_func=lambda _: "",
            out=io.StringIO(),
            runner=lambda command, cwd, env_overrides: calls.append((command, cwd, env_overrides)),
        )
        self.assertTrue(result.switch_environment)
        self.assertFalse(result.should_quit)
        self.assertEqual([], calls)

    def test_dispatch_action_propagates_backend_runner_failures(self) -> None:
        """Failure: backend execution errors are surfaced to the caller."""
        environment = self._targets()[0]
        with self.assertRaisesRegex(RuntimeError, "backend boom"):
            dispatch_action(
                "destroy",
                environment,
                input_func=lambda _: "",
                out=io.StringIO(),
                runner=lambda _command, _cwd, _env: (_ for _ in ()).throw(RuntimeError("backend boom")),
            )

    def test_parse_action_choice_accepts_shortcut_alias(self) -> None:
        """Expected: action parser maps aliases to canonical action keys."""
        self.assertEqual("quit", parse_action_choice("q"))


if __name__ == "__main__":
    unittest.main()
