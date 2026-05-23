"""Tests for PR3 Section B (loud failures) and E5 (FITSFixedWarning).

B1  — bg_coords clamp warning
B2  — core.dat epoch mismatch warning
B3  — validate() registry / bg-method check
B4  — _resolve_optional_file helper
B6  — select_files skips mask/ref/stack files
E5  — FITSFixedWarning suppressed at CLI entry
"""
import datetime
import os

import numpy as np
import pytest
from click.testing import CliRunner

pytest.importorskip("astropy")
fits = pytest.importorskip("astropy.io.fits")

import wise
from wise.cli import cli


# ---------------------------------------------------------------------------
# helpers shared across tests
# ---------------------------------------------------------------------------

def _write_fits(path, data, date_obs="2026-01-01"):
    """Write a minimal FITS file for testing."""
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
# B1: bg_coords clamp warning
# ---------------------------------------------------------------------------

def test_b1_clamp_warning_emitted(tmp_path, caplog):
    """get_bg emits WARNING when bg_coords extends beyond the image extent."""
    import logging
    from libwise import imgutils

    shape = (32, 32)
    data = np.ones(shape, dtype=np.float32) * 0.01
    fits_path = tmp_path / "img.fits"
    _write_fits(fits_path, data)

    ctx = wise.AnalysisContext()
    # bg_coords in sky coords (mas). The synthetic image is 32×32 pixels
    # at CDELT=1e-5 deg = 36 mas/pixel, CRPIX=16, so the half-width is
    # 16 * 36 = 576 mas. Set coords at ±5000 mas to guarantee clamping.
    ctx.config.data.bg_coords = [5000.0, -5000.0, 4000.0, -4000.0]

    img = imgutils.guess_and_open(str(fits_path))

    with caplog.at_level(logging.WARNING, logger="wise.project"):
        ctx.get_bg(img)

    clamp_msgs = [r for r in caplog.records if "clamped" in r.message]
    assert clamp_msgs, "Expected a clamp WARNING but none was emitted"


def test_b7_pixel_slice_logged_at_info(tmp_path, caplog):
    """get_bg always logs the resolved pixel slice at INFO level."""
    import logging
    from libwise import imgutils

    shape = (32, 32)
    data = np.ones(shape, dtype=np.float32) * 0.01
    fits_path = tmp_path / "img.fits"
    _write_fits(fits_path, data)

    ctx = wise.AnalysisContext()
    # Valid in-bounds coords (tiny region near the image centre)
    ctx.config.data.bg_coords = [0.01, -0.01, 0.005, -0.005]

    img = imgutils.guess_and_open(str(fits_path))

    with caplog.at_level(logging.INFO, logger="wise.project"):
        ctx.get_bg(img)

    slice_msgs = [r for r in caplog.records if "Background region" in r.message]
    assert slice_msgs, "Expected an INFO 'Background region' log line but none was found"


# ---------------------------------------------------------------------------
# B2: core.dat epoch mismatch warning
# ---------------------------------------------------------------------------

def test_b2_missing_epoch_warning(tmp_path, caplog):
    """align_img emits WARNING when the image epoch has no core.dat entry."""
    import logging
    from libwise import imgutils
    from wise import wiseutils

    shape = (32, 32)
    data = np.ones(shape, dtype=np.float32) * 0.01
    fits_path = tmp_path / "epoch_other.fits"
    _write_fits(fits_path, data, date_obs="2026-03-01")

    core_pos = wiseutils.CoreOffsetPositions()
    known_epoch = datetime.datetime(2026, 1, 1)
    core_pos.set(known_epoch, np.array([0.1, 0.2]))

    img = imgutils.guess_and_open(str(fits_path))
    prj = img.get_projection()

    with caplog.at_level(logging.WARNING, logger="wise.wiseutils"):
        core_pos.align_img(img, prj)

    warn_msgs = [r for r in caplog.records if "unaligned" in r.message]
    assert warn_msgs, "Expected a WARNING about missing epoch but none was emitted"


def test_b2_known_epoch_no_warning(tmp_path, caplog):
    """align_img does NOT warn when the epoch is present in core.dat."""
    import logging
    from libwise import imgutils
    from wise import wiseutils

    shape = (32, 32)
    data = np.ones(shape, dtype=np.float32) * 0.01
    fits_path = tmp_path / "epoch_known.fits"
    _write_fits(fits_path, data, date_obs="2026-01-01")

    core_pos = wiseutils.CoreOffsetPositions()
    known_epoch = datetime.datetime(2026, 1, 1)
    core_pos.set(known_epoch, np.array([0.0, 0.0]))

    img = imgutils.guess_and_open(str(fits_path))
    prj = img.get_projection()

    with caplog.at_level(logging.WARNING, logger="wise.wiseutils"):
        core_pos.align_img(img, prj)

    warn_msgs = [r for r in caplog.records if "unaligned" in r.message]
    assert not warn_msgs, "Unexpected WARNING for a known epoch"


# ---------------------------------------------------------------------------
# B3: validate() registry / bg-method check
# ---------------------------------------------------------------------------

def test_b3_validate_returns_issue_when_no_bg_method():
    """validate() returns a non-empty list when no background method is set."""
    config = wise.AnalysisConfiguration()
    # Defaults: bg_use_ksigma_method=False, bg_coords=None, bg_fct=None
    issues = config.validate()
    assert issues, "Expected at least one validation issue but got none"
    assert any("bg_coords" in issue or "bg_use_ksigma_method" in issue for issue in issues)


def test_b3_validate_clean_when_ksigma_set():
    """validate() returns empty list when bg_use_ksigma_method=True."""
    config = wise.AnalysisConfiguration()
    config.data.bg_use_ksigma_method = True
    issues = config.validate()
    assert issues == [], f"Expected no issues but got: {issues}"


def test_b3_validate_clean_when_bg_coords_set():
    """validate() returns empty list when bg_coords is configured."""
    config = wise.AnalysisConfiguration()
    config.data.bg_coords = [10.0, -10.0, 5.0, -5.0]
    issues = config.validate()
    assert issues == [], f"Expected no issues but got: {issues}"


def test_b3_validate_clean_when_bg_fct_set():
    """validate() returns empty list when bg_fct is configured."""
    config = wise.AnalysisConfiguration()
    config.data.bg_fct = lambda ctx, img: np.zeros(img.data.shape)
    issues = config.validate()
    assert issues == [], f"Expected no issues but got: {issues}"


# ---------------------------------------------------------------------------
# B4: _resolve_optional_file helper
# ---------------------------------------------------------------------------

def _init_project(tmp_path, monkeypatch):
    """Mark ``tmp_path`` as a wise project root and chdir into it.

    Mirrors what ``wise init`` does for tests that need
    :meth:`AnalysisContext.get_data_dir` to resolve to ``tmp_path``.
    """
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)


def test_b4_resolve_returns_none_for_unset_attr(tmp_path, monkeypatch):
    """_resolve_optional_file returns None when the config attr is None."""
    _init_project(tmp_path, monkeypatch)
    ctx = wise.AnalysisContext()
    ctx.config.data.mask_filename = None
    assert ctx._resolve_optional_file("mask_filename") is None


def test_b4_resolve_returns_none_for_missing_file(tmp_path, monkeypatch):
    """_resolve_optional_file returns None when the attr is set but the file is absent."""
    _init_project(tmp_path, monkeypatch)
    ctx = wise.AnalysisContext()
    ctx.config.data.mask_filename = "nonexistent_mask.fits"
    assert ctx._resolve_optional_file("mask_filename") is None


def test_b4_resolve_returns_path_when_file_exists(tmp_path, monkeypatch):
    """_resolve_optional_file returns the absolute path when the file exists."""
    _init_project(tmp_path, monkeypatch)
    mask_path = tmp_path / "mask.fits"
    mask_path.write_bytes(b"fake fits")

    ctx = wise.AnalysisContext()
    ctx.config.data.mask_filename = "mask.fits"
    resolved = ctx._resolve_optional_file("mask_filename")
    assert resolved is not None
    assert os.path.abspath(resolved) == os.path.abspath(str(mask_path))


# ---------------------------------------------------------------------------
# B6: select_files skips mask/ref/stack files
# ---------------------------------------------------------------------------

def test_b6_mask_file_skipped_with_warning(tmp_path, monkeypatch, caplog):
    """select_files drops the mask file from the input list and warns."""
    import logging

    _init_project(tmp_path, monkeypatch)

    shape = (32, 32)
    data = np.ones(shape, dtype=np.float32) * 0.01

    science_path = tmp_path / "science_2026_01_01.fits"
    mask_path = tmp_path / "mask.fits"
    _write_fits(science_path, data, date_obs="2026-01-01")
    _write_fits(mask_path, data, date_obs="2026-01-01")

    ctx = wise.AnalysisContext()
    ctx.config.data.mask_filename = "mask.fits"

    with caplog.at_level(logging.WARNING, logger="wise.project"):
        ctx.select_files([str(science_path), str(mask_path)])

    assert str(mask_path) not in ctx.files
    assert str(science_path) in ctx.files

    warn_msgs = [r for r in caplog.records if "mask_filename" in r.message]
    assert warn_msgs, "Expected WARNING about skipped mask file"


def test_b6_science_only_no_warning(tmp_path, monkeypatch, caplog):
    """select_files does not warn when no special files are in the input."""
    import logging

    _init_project(tmp_path, monkeypatch)

    shape = (32, 32)
    data = np.ones(shape, dtype=np.float32) * 0.01
    science_path = tmp_path / "science_2026_01_01.fits"
    _write_fits(science_path, data, date_obs="2026-01-01")

    ctx = wise.AnalysisContext()

    with caplog.at_level(logging.WARNING, logger="wise.project"):
        ctx.select_files([str(science_path)])

    assert len(ctx.files) == 1
    skip_msgs = [r for r in caplog.records
                 if "not a science image" in r.message]
    assert not skip_msgs


# ---------------------------------------------------------------------------
# E5: FITSFixedWarning suppressed at CLI entry
# ---------------------------------------------------------------------------

def test_e5_fits_fixed_warning_suppressed_in_cli(tmp_path, monkeypatch):
    """wise settings show does not surface FITSFixedWarning in output."""
    from astropy.wcs import FITSFixedWarning
    _init_project(tmp_path, monkeypatch)
    runner = CliRunner()
    # Invoke a CLI command that triggers _setup_logging — which installs the
    # warning filter — and capture all output including stderr mix-in.
    result = runner.invoke(cli, ["settings", "show", "data"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "FITSFixedWarning" not in result.output


# ---------------------------------------------------------------------------
# B3 CLI: wise settings show with broken config shows ⚠ banner
# ---------------------------------------------------------------------------

def test_b3_settings_show_issues_banner(tmp_path, monkeypatch):
    """wise settings show prints the ⚠ banner when no bg method is configured."""
    _init_project(tmp_path, monkeypatch)

    # Write a wise_config with no bg method set. Use the correct section name
    # ("Data configuration") as written by AnalysisConfiguration.to_file().
    config_path = tmp_path / "wise_config"
    config_path.write_text("[Data configuration]\nbg_use_ksigma_method = False\n")

    runner = CliRunner()
    result = runner.invoke(cli, ["settings", "show"], catch_exceptions=False)
    assert result.exit_code == 0, result.output
    assert "⚠" in result.output or "Configuration issues" in result.output
