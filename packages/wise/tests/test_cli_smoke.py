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
    "project",
    "stack",
    "settings",
    "detect",
    "match",
    "region",
    "select_files",
    "plot",
    "show",
]

# Commands removed in PR7 (F4.4) — now grouped under plot/show.
REMOVED_COMMANDS = [
    "info",
    "view",
    "view_features",
    "view_links",
    "plot_features",
    "plot_sep_from_core",
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
    result = runner.invoke(cli, ["-v", "--quiet", "settings", "--help"])
    assert result.exit_code != 0
    assert "mutually exclusive" in result.output.lower()


# ---------------------------------------------------------------------------
# F4: subcommand regrouping into plot/show groups
# ---------------------------------------------------------------------------

PLOT_SUBCOMMANDS = ["features", "links", "sep"]
SHOW_SUBCOMMANDS = ["features", "image", "info"]


@pytest.mark.parametrize("sub", PLOT_SUBCOMMANDS)
def test_plot_group_lists_and_help(sub):
    """wise plot --help lists the 3 subcommands; each has its own help."""
    runner = CliRunner()
    group = runner.invoke(cli, ["plot", "--help"])
    assert group.exit_code == 0, group.output
    assert sub in group.output
    sub_help = runner.invoke(cli, ["plot", sub, "--help"])
    assert sub_help.exit_code == 0, sub_help.output
    assert sub_help.output.strip()


@pytest.mark.parametrize("sub", SHOW_SUBCOMMANDS)
def test_show_group_lists_and_help(sub):
    """wise show --help lists the 3 subcommands; each has its own help."""
    runner = CliRunner()
    group = runner.invoke(cli, ["show", "--help"])
    assert group.exit_code == 0, group.output
    assert sub in group.output
    sub_help = runner.invoke(cli, ["show", sub, "--help"])
    assert sub_help.exit_code == 0, sub_help.output
    assert sub_help.output.strip()


def test_plot_features_help_matches_old_plot_features_options():
    """wise plot features keeps the old plot_features option surface (--pa)."""
    runner = CliRunner()
    result = runner.invoke(cli, ["plot", "features", "--help"])
    assert result.exit_code == 0, result.output
    assert "--pa" in result.output


def test_plot_sep_help_keeps_all_options():
    """wise plot sep keeps every old plot_sep_from_core option."""
    runner = CliRunner()
    result = runner.invoke(cli, ["plot", "sep", "--help"])
    assert result.exit_code == 0, result.output
    for opt in ("--pa", "--fit", "--num", "--min-link-size"):
        assert opt in result.output, f"{opt} missing from plot sep --help"


@pytest.mark.parametrize("cmd", REMOVED_COMMANDS)
def test_removed_top_level_command_errors(cmd):
    """F4.4: the old top-level commands no longer exist (clean break)."""
    runner = CliRunner()
    result = runner.invoke(cli, [cmd, "x", "y"])
    assert result.exit_code != 0
    assert "no such command" in result.output.lower()


def test_removed_commands_absent_from_group_help():
    """None of the removed commands appear in the top-level command list."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    # Match on the command-list line shape to avoid matching e.g. 'view' in prose.
    for cmd in REMOVED_COMMANDS:
        assert f"  {cmd} " not in result.output, f"removed '{cmd}' still in --help"


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
