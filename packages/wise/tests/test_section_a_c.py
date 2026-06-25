"""Tests for PR6: renames (A4, C3), int-keyed dict tolerance (C4/C5),
the A2 fallback, and the require_project_root hygiene helper.

A4 — --nsigma_connected -> --keep_brightest_only (CLI rename, BREAKING)
C3 — alpha_threashold -> alpha_threshold (config key rename, BREAKING)
C4/C5 — decode_scale_dict int/float-key tolerance
A2 — wise match re-detect notice + reworded save prompts (fallback)
Hygiene 1 — require_project_root() centralizes ProjectRootNotFound
"""
import os

import numpy as np
import pytest
from click.testing import CliRunner

pytest.importorskip("astropy")
fits = pytest.importorskip("astropy.io.fits")

import click  # noqa: E402

import wise  # noqa: E402
from wise import actions  # noqa: E402  (wise.actions.actions re-exported)
from wise.actions import actions as actions_mod  # noqa: E402
from wise.cli import cli  # noqa: E402
from wise.project import decode_scale_dict  # noqa: E402


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _write_fits(path, data, date_obs="2026-01-01"):
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
    hdu.writeto(str(path), overwrite=True)


# ---------------------------------------------------------------------------
# A4: --nsigma_connected -> --keep_brightest_only
# ---------------------------------------------------------------------------

def test_a4_keep_brightest_only_exits_zero(tmp_path):
    """wise stack ... --keep_brightest_only exits 0."""
    shape = (32, 32)
    data = np.random.default_rng(0).normal(1, 0.01, shape).astype(np.float32)
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        os.makedirs(".wise")
        _write_fits("img.fits", data)
        runner.invoke(cli, ["settings", "set", "data.bg_use_ksigma_method=True"])
        result = runner.invoke(
            cli, ["stack", "img.fits", "--keep_brightest_only", "-o", "out.fits"]
        )
    assert result.exit_code == 0, result.output


def test_a4_short_option_preserved(tmp_path):
    """The -c short option still maps to --keep_brightest_only."""
    shape = (32, 32)
    data = np.random.default_rng(1).normal(1, 0.01, shape).astype(np.float32)
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        os.makedirs(".wise")
        _write_fits("img.fits", data)
        runner.invoke(cli, ["settings", "set", "data.bg_use_ksigma_method=True"])
        result = runner.invoke(cli, ["stack", "img.fits", "-c", "-o", "out.fits"])
    assert result.exit_code == 0, result.output


def test_a4_old_flag_errors_with_rename_message(tmp_path):
    """wise stack ... --nsigma_connected exits nonzero with the rename message."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        os.makedirs(".wise")
        result = runner.invoke(cli, ["stack", "img.fits", "--nsigma_connected"])
    assert result.exit_code != 0
    assert "--keep_brightest_only" in result.output
    assert "renamed" in result.output.lower()


def test_a4_hidden_flag_absent_from_help():
    """wise stack --help lists --keep_brightest_only, not --nsigma_connected."""
    runner = CliRunner()
    result = runner.invoke(cli, ["stack", "--help"])
    assert result.exit_code == 0
    assert "--keep_brightest_only" in result.output
    assert "--nsigma_connected" not in result.output


# ---------------------------------------------------------------------------
# C3: alpha_threashold -> alpha_threshold
# ---------------------------------------------------------------------------

def test_c3_new_key_runtime():
    """A finder config with alpha_threshold set behaves as expected."""
    cfg = wise.AnalysisConfiguration()
    cfg.finder.alpha_threshold = 7.5
    assert cfg.finder.get("alpha_threshold") == 7.5


def test_c3_old_key_raises_option_renamed():
    """Reading the old typo key raises OptionRenamedError carrying both names."""
    from libwise.nputils import OptionRenamedError

    cfg = wise.AnalysisConfiguration()
    with pytest.raises(OptionRenamedError) as exc:
        cfg.finder.get("alpha_threashold")
    assert exc.value.old_name == "alpha_threashold"
    assert exc.value.new_name == "alpha_threshold"


def test_c3_config_load_raises_usage_error(tmp_path, monkeypatch):
    """A wise_config with the old key produces a click.UsageError on load,
    naming both keys and pointing at wise upgrade-config."""
    (tmp_path / ".wise").mkdir()
    (tmp_path / "wise_config").write_text(
        "[Finder configuration]\nalpha_threashold = 3\n"
    )
    monkeypatch.chdir(tmp_path)
    with pytest.raises(click.UsageError) as exc:
        actions_mod.get_config(False)
    msg = str(exc.value)
    assert "alpha_threashold" in msg
    assert "alpha_threshold" in msg
    assert "wise upgrade-config" in msg


# ---------------------------------------------------------------------------
# C4/C5: decode_scale_dict
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,expected,keytype",
    [
        ("{4: 1.0}", {4: 1.0}, int),       # literal int keys
        ('{"4": 1.0}', {4: 1.0}, int),     # JSON string keys
        ("{4.0: 1.0}", {4.0: 1.0}, float), # literal float keys
        ('{"4.0": 1.0}', {4.0: 1.0}, float),  # JSON string floats
    ],
)
def test_c4_decode_scale_dict_forms(raw, expected, keytype):
    d = decode_scale_dict(raw)
    assert d == expected
    assert all(isinstance(k, keytype) for k in d)


def test_c4_decode_scale_dict_roundtrip():
    """jp.encode (JSON string keys) then decode_scale_dict yields an equal
    int-keyed dict."""
    import jsonpickle as jp

    original = {4: 4.0, 6: 4.0}
    decoded = decode_scale_dict(jp.encode(original))
    assert decoded == original
    assert all(isinstance(k, int) for k in decoded)


def test_c4_scales_snr_filter_uses_decoder():
    """finder.scales_snr_filter decodes int-keyed literal form to int keys."""
    cfg = wise.AnalysisConfiguration()
    cfg.finder.set("scales_snr_filter", "{4: 3.0}", decode=True)
    val = cfg.finder.get("scales_snr_filter")
    assert val == {4: 3.0}
    assert all(isinstance(k, int) for k in val)


def test_c5_min_scale_tolerance_uses_decoder():
    """matcher.min_scale_tolerance decodes JSON string keys to int keys."""
    cfg = wise.AnalysisConfiguration()
    cfg.matcher.set("min_scale_tolerance", '{"2": 4, "3": 4}', decode=True)
    val = cfg.matcher.get("min_scale_tolerance")
    assert val == {2: 4, 3: 4}
    assert all(isinstance(k, int) for k in val)


# ---------------------------------------------------------------------------
# A2 fallback: re-detect notice + reworded save prompts
# ---------------------------------------------------------------------------

def test_a2_match_prints_redetect_notice(tmp_path):
    """wise match prints the re-detect notice by default."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        os.makedirs(".wise")
        # Glob that matches no files -> match returns cleanly after the notice.
        result = runner.invoke(cli, ["match", "--no-save", "no_such_*.fits"])
    assert "re-runs detection" in result.output
    assert "centroids only" in result.output


def test_a2_match_notice_suppressed_with_quiet(tmp_path):
    """--quiet suppresses the re-detect notice."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        os.makedirs(".wise")
        result = runner.invoke(cli, ["-q", "match", "--no-save", "no_such_*.fits"])
    assert "re-runs detection" not in result.output


def test_a2_detect_save_prompt_reworded(tmp_path):
    """The detect save prompt clarifies the result is for plotting only."""
    shape = (32, 32)
    data = np.random.default_rng(2).normal(0, 0.01, shape).astype(np.float32)
    data[16, 16] = 5.0
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        os.makedirs(".wise")
        _write_fits("img.fits", data)
        runner.invoke(cli, ["settings", "set", "data.bg_use_ksigma_method=True"])
        # Decline the save prompt (input "n"); --view-scales "" skips the loop.
        result = runner.invoke(
            cli, ["detect", "img.fits", "--view-scales", ""], input="n\n"
        )
    assert "Save detection for plotting only?" in result.output


# ---------------------------------------------------------------------------
# Hygiene 1: require_project_root centralizes the ProjectRootNotFound message
# ---------------------------------------------------------------------------

_NO_ROOT_MESSAGE_FRAGMENT = "no project root found"


def test_hygiene1_require_project_root_returns_root(tmp_path, monkeypatch):
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    assert wise.require_project_root() == str(tmp_path.resolve())


def test_hygiene1_require_project_root_raises(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no .wise here or above (pytest tmp)
    with pytest.raises(wise.ProjectRootNotFound, match=_NO_ROOT_MESSAGE_FRAGMENT):
        wise.require_project_root()


@pytest.mark.parametrize(
    "invoke",
    [
        pytest.param(lambda: wise.require_project_root(), id="require_project_root"),
        pytest.param(lambda: actions_mod.get_config_path(), id="get_config_path"),
        pytest.param(lambda: actions_mod.load("anything"), id="actions.load"),
    ],
)
def test_hygiene1_message_consistent_across_call_sites(tmp_path, monkeypatch, invoke):
    """Every project-requiring entry point raises the same message."""
    monkeypatch.chdir(tmp_path)
    with pytest.raises(wise.ProjectRootNotFound) as exc:
        invoke()
    assert _NO_ROOT_MESSAGE_FRAGMENT in str(exc.value)


@pytest.mark.parametrize("args", [["project"], ["settings", "show"]])
def test_hygiene1_cli_sites_consistent(tmp_path, monkeypatch, args):
    """CLI commands needing a project print the shared message when none found."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(cli, args)
    assert result.exit_code != 0
    assert _NO_ROOT_MESSAGE_FRAGMENT in result.output
