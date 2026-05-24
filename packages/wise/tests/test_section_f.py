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


# ---------------------------------------------------------------------------
# F5: <name>.wiseproj/ bundle layout
# ---------------------------------------------------------------------------

import json  # noqa: E402

import click  # noqa: E402
import numpy as np  # noqa: E402

fits = pytest.importorskip("astropy.io.fits")


def _gaussian_2d(shape, center, sigma=2.5, amplitude=1.0):
    yy, xx = np.indices(shape)
    cy, cx = center
    return amplitude * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2))


def _write_fits(path, data, date_obs):
    hdu = fits.PrimaryHDU(data.astype(np.float32))
    hdu.header["DATE-OBS"] = date_obs
    hdu.header["BMAJ"] = 1e-4
    hdu.header["BMIN"] = 1e-4
    hdu.header["BPA"] = 0.0
    hdu.header["CRVAL1"] = 0.0
    hdu.header["CRVAL2"] = 0.0
    hdu.header["CRPIX1"] = data.shape[1] / 2
    hdu.header["CRPIX2"] = data.shape[0] / 2
    hdu.header["CDELT1"] = -1e-5
    hdu.header["CDELT2"] = 1e-5
    hdu.header["CTYPE1"] = "RA---SIN"
    hdu.header["CTYPE2"] = "DEC--SIN"
    hdu.writeto(path, overwrite=True)


@pytest.fixture
def matched_ctx(tmp_path, monkeypatch):
    """A project-rooted ctx carrying a real 2-epoch detection+match result.

    Mirrors test_smoke_pipeline's synthetic dataset, then runs match_all so
    detection / image_set / link_builder are all populated for save/load.
    """
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)

    shape = (64, 64)
    rng = np.random.default_rng(42)
    noise = 0.001
    epoch1 = (
        _gaussian_2d(shape, (32, 24), sigma=3.0, amplitude=1.0)
        + _gaussian_2d(shape, (32, 42), sigma=2.5, amplitude=0.6)
        + rng.normal(0, noise, shape)
    )
    epoch2 = (
        _gaussian_2d(shape, (32, 25), sigma=3.0, amplitude=1.0)
        + _gaussian_2d(shape, (33, 43), sigma=2.5, amplitude=0.6)
        + rng.normal(0, noise, shape)
    )
    paths = []
    try:
        for i, (data, date) in enumerate([(epoch1, "2026-01-01"), (epoch2, "2026-02-01")]):
            p = tmp_path / f"epoch_{i:02d}.fits"
            _write_fits(str(p), data, date)
            paths.append(str(p))
        # A dedicated reference image (distinct from the science inputs, so
        # select_files doesn't filter it out). Only its WCS is used, for the
        # projection. A real project's saved config carries such a pointer;
        # the loader reads it back from config.wise_config.
        ref_path = tmp_path / "ref.fits"
        _write_fits(str(ref_path), epoch1, "2026-01-01")
    except Exception as e:  # pragma: no cover
        pytest.skip(f"FITS write failed in test environment: {e}")

    ctx = wise.AnalysisContext()
    ctx.config.finder.min_scale = 2
    ctx.config.finder.max_scale = 3
    ctx.config.finder.alpha_threshold = 10
    ctx.config.finder.alpha_detection = 15
    ctx.config.data.bg_use_ksigma_method = True
    ctx.config.data.ref_image_filename = str(ref_path)
    ctx.select_files(paths)
    wise.tasks.match_all(ctx)
    return ctx, str(ref_path)


def test_save_creates_wiseproj_bundle(matched_ctx, tmp_path):
    """F5.1: save writes a <name>.wiseproj/ bundle with manifest + data files."""
    ctx, _paths = matched_ctx
    wise.tasks.save(ctx, "result1")
    bundle = tmp_path / "result1.wiseproj"
    assert bundle.is_dir()
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "detection.dat").is_file()
    assert (bundle / "image_set.dat").is_file()
    assert (bundle / "config.wise_config").is_file()
    # No old-layout artifacts.
    assert not list(tmp_path.glob("result1/*.set.dat"))


def test_manifest_schema(matched_ctx, tmp_path):
    """F5.2: manifest.json has the expected keys and schema_version '1.0'."""
    ctx, _paths = matched_ctx
    wise.tasks.save(ctx, "result1")
    manifest = json.loads((tmp_path / "result1.wiseproj" / "manifest.json").read_text())
    assert manifest["schema_version"] == "1.0"
    assert manifest["name"] == "result1"
    assert manifest["wise_version"] == wise.__version__
    assert "created" in manifest
    files = manifest["files"]
    assert files["detection"] == "detection.dat"
    assert files["image_set"] == "image_set.dat"
    assert files["config"] == "config.wise_config"
    assert isinstance(files["links"], list)
    for link_file in files["links"]:
        assert link_file.startswith("links_") and link_file.endswith(".dfc.dat")
        assert (tmp_path / "result1.wiseproj" / link_file).is_file()


def test_save_load_roundtrip(matched_ctx, tmp_path):
    """F5.1 round-trip: a loaded bundle reproduces the saved scales/epochs."""
    ctx, ref_path = matched_ctx
    wise.tasks.save(ctx, "result1")
    saved_scales = ctx.result.get_scales()
    saved_epochs = ctx.result.image_set.get_epochs()

    ctx2 = wise.AnalysisContext()
    ctx2.config.data.ref_image_filename = ref_path
    wise.tasks.load(ctx2, "result1")
    assert ctx2.result.get_scales() == saved_scales
    assert ctx2.result.image_set.get_epochs() == saved_epochs
    assert ctx2.result.has_detection_result()


def test_save_refuses_to_overwrite(matched_ctx, tmp_path):
    """F5.1 collision: saving onto an existing bundle raises UsageError."""
    ctx, _paths = matched_ctx
    wise.tasks.save(ctx, "result1")
    with pytest.raises(click.UsageError, match="already exists"):
        wise.tasks.save(ctx, "result1")


def test_load_missing_bundle_raises(tmp_path, monkeypatch):
    """Loading an unknown name raises a plain UsageError."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    ctx = wise.AnalysisContext()
    with pytest.raises(click.UsageError, match="No saved result named"):
        wise.tasks.load(ctx, "ghost")


def test_load_old_layout_points_at_migration(tmp_path, monkeypatch):
    """F5.4: a sibling 0.5/0.6 result dir yields the wise upgrade-config hint."""
    (tmp_path / ".wise").mkdir()
    old = tmp_path / "legacy"
    old.mkdir()
    (old / "legacy.set.dat").write_text("")
    monkeypatch.chdir(tmp_path)
    ctx = wise.AnalysisContext()
    with pytest.raises(click.UsageError, match="wise upgrade-config"):
        wise.tasks.load(ctx, "legacy")


def test_read_manifest_rejects_other_schema(tmp_path, monkeypatch):
    """_read_manifest gates on schema_version != '1.0'."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    bundle = tmp_path / "future.wiseproj"
    bundle.mkdir()
    (bundle / "manifest.json").write_text(json.dumps({"schema_version": "2.0"}))
    with pytest.raises(ValueError, match="schema_version"):
        wise.tasks._read_manifest(str(bundle))


def test_actions_load_reads_bundle(matched_ctx, tmp_path):
    """actions.load (the show/plot discoverer) resolves a .wiseproj bundle."""
    ctx, _paths = matched_ctx
    wise.tasks.save(ctx, "result1")
    loaded = actions.load("result1")
    assert loaded is not None
    assert loaded.result.get_scales() == ctx.result.get_scales()
