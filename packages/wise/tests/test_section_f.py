"""Tests for PR5 Section F project-root mode.

F3.1 — find_project_root resolver
F3.2 — wise init command (creates wise_config + .wise/ + .gitignore entry)
F3.3 — AnalysisContext.get_data_dir uses project root; data.data_dir gone
F3.4 — wise info --project flag
F3.5 — wise settings show "Project root:" header
F3.6 — actions.get_config / get_config_path read from project root
"""
import os

import pytest
from click.testing import CliRunner

import wise
from wise.actions import actions
from wise.cli import cli


# ---------------------------------------------------------------------------
# F3.1: find_project_root
# ---------------------------------------------------------------------------

def test_find_project_root_returns_none_outside_any_project(tmp_path, monkeypatch):
    """Outside any .wise/ ancestor, the resolver returns None."""
    monkeypatch.chdir(tmp_path)
    assert wise.find_project_root() is None


def test_find_project_root_finds_marker_in_cwd(tmp_path, monkeypatch):
    """When .wise/ is in cwd, returns abspath(cwd) — not the marker itself."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    root = wise.find_project_root()
    assert root == str(tmp_path.resolve())
    assert not root.endswith(".wise")


def test_find_project_root_walks_upward_from_nested(tmp_path, monkeypatch):
    """From a deeply-nested cwd, walks upward to the .wise/ ancestor."""
    (tmp_path / ".wise").mkdir()
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    assert wise.find_project_root() == str(tmp_path.resolve())


def test_find_project_root_accepts_explicit_start(tmp_path):
    """An explicit start argument is honored over cwd."""
    (tmp_path / ".wise").mkdir()
    nested = tmp_path / "x" / "y"
    nested.mkdir(parents=True)
    assert wise.find_project_root(start=str(nested)) == str(tmp_path.resolve())


# ---------------------------------------------------------------------------
# F3.2: wise init
# ---------------------------------------------------------------------------

def test_wise_init_creates_marker_and_config(tmp_path):
    """wise init <dir> creates both .wise/ and wise_config."""
    runner = CliRunner()
    target = tmp_path / "proj"
    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 0, result.output
    assert (target / ".wise").is_dir()
    assert (target / "wise_config").is_file()
    assert "Initialized wise project at" in result.output
    assert "created wise_config + .wise/" in result.output


def test_wise_init_preserves_existing_config(tmp_path):
    """wise init does not overwrite an existing wise_config."""
    runner = CliRunner()
    target = tmp_path / "proj"
    target.mkdir()
    (target / "wise_config").write_text("[Data configuration]\nbg_use_ksigma_method = True\n")

    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 0, result.output
    assert (target / ".wise").is_dir()
    # Existing content is preserved
    content = (target / "wise_config").read_text()
    assert "bg_use_ksigma_method = True" in content
    assert "found existing wise_config; added .wise/" in result.output


def test_wise_init_refuses_to_reinit(tmp_path):
    """wise init errors when .wise/ already exists."""
    runner = CliRunner()
    target = tmp_path / "proj"
    target.mkdir()
    (target / ".wise").mkdir()

    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code != 0
    assert "already exists" in result.output
    assert "Refusing to re-initialize" in result.output


def test_wise_init_default_directory_is_cwd(tmp_path, monkeypatch):
    """wise init with no argument uses cwd."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["init"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / ".wise").is_dir()
    assert (tmp_path / "wise_config").is_file()


def test_wise_init_creates_gitignore_when_missing(tmp_path):
    """wise init creates .gitignore with the .wise/ entry when none exists."""
    runner = CliRunner()
    target = tmp_path / "proj"
    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 0, result.output
    gi = (target / ".gitignore").read_text()
    assert ".wise/" in gi


def test_wise_init_appends_to_existing_gitignore(tmp_path):
    """wise init appends .wise/ to an existing .gitignore without duplicating."""
    runner = CliRunner()
    target = tmp_path / "proj"
    target.mkdir()
    (target / ".gitignore").write_text("*.pyc\n__pycache__/\n")

    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 0, result.output
    gi = (target / ".gitignore").read_text()
    assert "*.pyc" in gi  # original preserved
    assert ".wise/" in gi  # new entry appended


def test_wise_init_gitignore_idempotent(tmp_path):
    """An existing .gitignore already listing .wise/ is not modified."""
    runner = CliRunner()
    target = tmp_path / "proj"
    target.mkdir()
    original = "node_modules/\n.wise/\n"
    (target / ".gitignore").write_text(original)

    result = runner.invoke(cli, ["init", str(target)])
    assert result.exit_code == 0, result.output
    assert (target / ".gitignore").read_text() == original


# ---------------------------------------------------------------------------
# F3.3: get_data_dir uses project root; data.data_dir removed
# ---------------------------------------------------------------------------

def test_data_dir_field_is_gone():
    """data_dir is no longer a DataConfiguration setting."""
    config = wise.AnalysisConfiguration()
    assert "data_dir" not in config.data._keys


def test_get_data_dir_raises_outside_project(tmp_path, monkeypatch):
    """AnalysisContext.get_data_dir raises ProjectRootNotFound with no .wise/."""
    monkeypatch.chdir(tmp_path)
    ctx = wise.AnalysisContext()
    with pytest.raises(wise.ProjectRootNotFound, match="no project root found"):
        ctx.get_data_dir()


def test_get_data_dir_returns_project_root(tmp_path, monkeypatch):
    """AnalysisContext.get_data_dir returns the abspath of the project root."""
    (tmp_path / ".wise").mkdir()
    nested = tmp_path / "deep" / "nested"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    ctx = wise.AnalysisContext()
    assert ctx.get_data_dir() == str(tmp_path.resolve())


def test_project_root_not_found_is_click_usage_error():
    """ProjectRootNotFound subclasses click.UsageError so click exits 2."""
    import click
    assert issubclass(wise.ProjectRootNotFound, click.UsageError)


# ---------------------------------------------------------------------------
# F4.3: wise project (replaces the PR5 `wise info --project` flag)
# ---------------------------------------------------------------------------

def test_project_prints_root(tmp_path, monkeypatch):
    """wise project prints the resolved root and exits 0."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["project"])
    assert result.exit_code == 0, result.output
    assert str(tmp_path.resolve()) in result.output


def test_project_errors_outside_project(tmp_path, monkeypatch):
    """wise project errors when no project root is found."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["project"])
    assert result.exit_code != 0
    assert "no project root" in result.output


def test_project_walks_upward(tmp_path, monkeypatch):
    """wise project from a nested cwd resolves to the parent root."""
    (tmp_path / ".wise").mkdir()
    nested = tmp_path / "subdir"
    nested.mkdir()
    monkeypatch.chdir(nested)

    runner = CliRunner()
    result = runner.invoke(cli, ["project"])
    assert result.exit_code == 0, result.output
    assert str(tmp_path.resolve()) in result.output


def test_info_project_flag_removed(tmp_path, monkeypatch):
    """The old `wise info --project` flag is gone (absorbed into wise project)."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["info", "--project"])
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


# ---------------------------------------------------------------------------
# F3.5: wise settings show "Project root:" header
# ---------------------------------------------------------------------------

def test_settings_show_includes_project_root_header(tmp_path, monkeypatch):
    """wise settings show emits the 'Project root: <abs>' header line."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(cli, ["settings", "show"])
    assert result.exit_code == 0, result.output
    assert "Project root:" in result.output
    assert str(tmp_path.resolve()) in result.output


def test_settings_show_errors_outside_project(tmp_path, monkeypatch):
    """wise settings show errors when there is no project root."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, ["settings", "show"])
    assert result.exit_code != 0
    assert "no project root" in result.output


# ---------------------------------------------------------------------------
# F3.6: actions.get_config reads wise_config from project root
# ---------------------------------------------------------------------------

def test_get_config_reads_wise_config_from_root(tmp_path, monkeypatch):
    """actions.get_config loads wise_config sitting at the project root."""
    (tmp_path / ".wise").mkdir()
    (tmp_path / "wise_config").write_text(
        "[Data configuration]\nbg_use_ksigma_method = True\n"
    )
    monkeypatch.chdir(tmp_path)

    config = actions.get_config(False)
    assert config.data.bg_use_ksigma_method is True


def test_get_config_creates_default_at_root(tmp_path, monkeypatch):
    """actions.get_config(create_if_none=True) writes wise_config to the root."""
    (tmp_path / ".wise").mkdir()
    nested = tmp_path / "sub"
    nested.mkdir()
    monkeypatch.chdir(nested)

    config = actions.get_config(True)
    assert (tmp_path / "wise_config").is_file()
    assert config is not None


def test_get_config_outside_project_returns_default(tmp_path, monkeypatch):
    """actions.get_config outside any project returns a default config (no error)."""
    monkeypatch.chdir(tmp_path)
    config = actions.get_config(False)
    assert isinstance(config, wise.AnalysisConfiguration)


def test_get_config_path_raises_outside_project(tmp_path, monkeypatch):
    """actions.get_config_path raises ProjectRootNotFound outside any project."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(wise.ProjectRootNotFound):
        actions.get_config_path()


def test_get_config_path_returns_root_config(tmp_path, monkeypatch):
    """actions.get_config_path returns <project_root>/wise_config."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    assert actions.get_config_path() == os.path.join(str(tmp_path.resolve()), "wise_config")
