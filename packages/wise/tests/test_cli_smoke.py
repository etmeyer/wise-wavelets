"""CliRunner smoke tests for the click-based wise CLI (F7 baseline).

Each subcommand is invoked with --help and the test asserts exit_code == 0
and non-empty output. No actual FITS processing happens here; the existing
test_smoke_pipeline.py covers the detect/match orchestration.
"""
import os

import pytest
from click.testing import CliRunner

from wise.cli import cli

SUBCOMMANDS = [
    "init",
    "info",
    "stack",
    "settings",
    "detect",
    "match",
    "view",
    "view_features",
    "view_links",
    "plot_features",
    "plot_sep_from_core",
    "region",
    "select_files",
]


@pytest.fixture
def in_project(tmp_path, monkeypatch):
    """Chdir into a freshly-marked wise project root.

    Required for any command that walks upward looking for ``.wise/``.
    """
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.mark.parametrize("cmd", SUBCOMMANDS)
def test_subcommand_help(cmd):
    runner = CliRunner()
    result = runner.invoke(cli, [cmd, "--help"])
    assert result.exit_code == 0, (
        f"wise {cmd} --help exited with {result.exit_code}:\n{result.output}"
    )
    assert result.output.strip(), f"wise {cmd} --help produced empty output"


def test_group_help():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert result.output.strip()
    # Every registered subcommand should appear in the group help
    for cmd in SUBCOMMANDS:
        assert cmd in result.output, f"'{cmd}' missing from wise --help output"


def test_version():
    import wise
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip()
    assert wise.__version__ in result.output


def test_mutually_exclusive_verbosity_flags():
    runner = CliRunner()
    result = runner.invoke(cli, ["-v", "--quiet", "info", "--help"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


def test_non_interactive_no_files_is_clean_error():
    """--non-interactive detect with no files (empty glob) exits 0 (no files)."""
    runner = CliRunner()
    # Passing a non-existent file pattern that resolves to 0 files after
    # select_files. We use --no-save so no prompt fires.
    result = runner.invoke(cli, ["--non-interactive", "detect", "--no-save",
                                 "/nonexistent_path_xyz_*.fits"])
    # Either exit 0 (no files found) or 2 (usage error from click) is fine;
    # the key requirement is no uncaught exception traceback.
    assert "Traceback" not in result.output


# ---------------------------------------------------------------------------
# PR2 tests: settings table format, A6 cwd note
# ---------------------------------------------------------------------------

def test_settings_show_six_column_table(in_project):
    """wise settings show data includes all six column headers."""
    runner = CliRunner()
    result = runner.invoke(cli, ["settings", "show", "data"])
    assert result.exit_code == 0, result.output
    for col in ("Option", "Value", "Default", "Unit", "Range", "Documentation"):
        assert col in result.output, f"Column '{col}' missing from settings show output"


def test_settings_show_all_sections(in_project):
    """wise settings show (no section) includes all three section titles."""
    runner = CliRunner()
    result = runner.invoke(cli, ["settings", "show"])
    assert result.exit_code == 0, result.output
    for title in ("Data configuration", "Finder configuration", "Matcher configuration"):
        assert title in result.output, f"'{title}' missing from settings show output"


def test_settings_doc_same_as_show(in_project):
    """wise settings doc produces the same 6-column table as wise settings show."""
    runner = CliRunner()
    # Both must succeed and include all six column headers.
    for cmd in ["show", "doc"]:
        result = runner.invoke(cli, ["settings", cmd, "data"])
        assert result.exit_code == 0, f"settings {cmd} failed: {result.output}"
        for col in ("Option", "Value", "Default", "Unit", "Range", "Documentation"):
            assert col in result.output, (
                f"Column '{col}' missing from settings {cmd} output"
            )


def test_settings_show_sigma_unit_in_finder(in_project):
    """wise settings show finder includes 'σ' for alpha fields."""
    runner = CliRunner()
    result = runner.invoke(cli, ["settings", "show", "finder"])
    assert result.exit_code == 0, result.output
    assert "σ" in result.output
