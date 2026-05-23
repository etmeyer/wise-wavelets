"""Tests for PR4 Section C (config clarity) and hygiene sweep.

C1  — compute_scales_widths formula extraction + settings show finder footer
C2  — detection_preview() analytics + wise detect --dry-run CLI
Hygiene #3 — save_core_offset_pos_file ValueError when filename unset
Hygiene #4 — get_stack_image raises RuntimeError (not bare Exception)
"""
import os

import numpy as np
import pytest
from click.testing import CliRunner

pytest.importorskip("astropy")
fits = pytest.importorskip("astropy.io.fits")

import wise
from wise.cli import cli
from wise.wds import compute_scales_widths


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


def _gaussian_2d(shape, center, amplitude, sigma):
    y, x = np.mgrid[: shape[0], : shape[1]]
    cy, cx = center
    return amplitude * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * sigma ** 2))


# ---------------------------------------------------------------------------
# C1: compute_scales_widths formula extraction
# ---------------------------------------------------------------------------

def test_c1_formula_b1():
    """compute_scales_widths(1, 5, 'b1') matches original inline formula."""
    result = compute_scales_widths(1, 5, "b1")
    assert result == [2, 4, 8, 16]


def test_c1_formula_b3():
    """compute_scales_widths(1, 5, 'b3') uses the b3 multiplier."""
    result = compute_scales_widths(1, 5, "b3")
    assert result == [3.0, 6.0, 12.0, 24.0]


def test_c1_formula_triangle2_uses_b3_branch():
    """triangle2 uses the same branch as b3."""
    b3_result = compute_scales_widths(1, 4, "b3")
    tri_result = compute_scales_widths(1, 4, "triangle2")
    assert tri_result == b3_result


def test_c1_formula_empty_range():
    """min_scale == max_scale returns empty list."""
    assert compute_scales_widths(2, 2, "b1") == []


# ---------------------------------------------------------------------------
# C1: settings show finder footer
# ---------------------------------------------------------------------------

def test_c1_footer_present_in_show_finder(tmp_path):
    """wise settings show finder includes 'Resulting widths:' line."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["settings", "show", "finder"])
    assert result.exit_code == 0, result.output
    assert "Resulting widths:" in result.output


def test_c1_footer_values_match_formula(tmp_path):
    """Finder footer lists the widths matching compute_scales_widths for defaults."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["settings", "show", "finder"])
    assert result.exit_code == 0
    # Default config: min_scale=1, max_scale=4, wd_wavelet='b1', use_iwd=False
    expected = compute_scales_widths(1, 4, "b1")
    expected_str = str([int(w) if w == int(w) else w for w in expected])
    assert expected_str in result.output


def test_c1_footer_present_in_show_all(tmp_path):
    """wise settings show (all sections) also shows the finder footer."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["settings", "show"])
    assert result.exit_code == 0
    assert "Resulting widths:" in result.output


def test_c1_footer_iwd_mentions_both_wavelets(tmp_path):
    """When use_iwd=True, the footer mentions both wavelet names."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        runner.invoke(cli, ["settings", "set", "finder.use_iwd=True"])
        result = runner.invoke(cli, ["settings", "show", "finder"])
    assert result.exit_code == 0
    assert "use_iwd=True" in result.output
    # Both wavelet names should appear (e.g. b1+b3)
    assert "b1" in result.output and "b3" in result.output


# ---------------------------------------------------------------------------
# C2: detection_preview analytics
# ---------------------------------------------------------------------------

def test_c2_detection_preview_returns_stats(tmp_path):
    """detection_preview returns one dict per decomposed scale."""
    shape = (64, 64)
    noise = np.random.default_rng(0).normal(0, 0.01, shape).astype(np.float32)
    # inject a bright Gaussian peak so at least one scale has detections
    peak = _gaussian_2d(shape, (32, 32), amplitude=0.5, sigma=2.0).astype(np.float32)
    data = noise + peak
    fits_path = tmp_path / "src.fits"
    _write_fits(fits_path, data)

    ctx = wise.AnalysisContext()
    ctx.config.data.data_dir = str(tmp_path)
    ctx.config.data.bg_use_ksigma_method = True
    # default min_scale=1, max_scale=4 → 3 decomposed scales
    ctx.config.finder.set("min_scale", 1)
    ctx.config.finder.set("max_scale", 4)

    stats = wise.tasks.detection_preview(ctx, str(fits_path))

    assert isinstance(stats, list)
    assert len(stats) == 3  # max_scale - min_scale = 3

    for entry in stats:
        assert "scale" in entry
        assert "width" in entry
        assert "noise" in entry
        assert "n_above" in entry
        assert "n_between" in entry

    # The injected peak should be detectable in at least one scale
    total_detected = sum(s["n_above"] + s["n_between"] for s in stats)
    assert total_detected >= 1


# ---------------------------------------------------------------------------
# C2: wise detect --dry-run CLI
# ---------------------------------------------------------------------------

def test_c2_dry_run_exits_zero(tmp_path):
    """wise detect --dry-run on a single file exits 0 and prints expected headers."""
    shape = (64, 64)
    noise = np.random.default_rng(1).normal(0, 0.01, shape).astype(np.float32)
    peak = _gaussian_2d(shape, (32, 32), amplitude=0.5, sigma=2.0).astype(np.float32)
    data = noise + peak
    fits_path = tmp_path / "src.fits"
    _write_fits(fits_path, data)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        # set bg method so detection can proceed
        runner.invoke(cli, ["settings", "set", "data.bg_use_ksigma_method=True"])
        result = runner.invoke(cli, ["detect", "--dry-run", str(fits_path)])

    assert result.exit_code == 0, result.output
    assert "Detection preview" in result.output
    assert "Above α=" in result.output


def test_c2_dry_run_multi_file_rejected(tmp_path):
    """wise detect --dry-run with two files exits nonzero with a UsageError."""
    shape = (32, 32)
    data = np.ones(shape, dtype=np.float32)
    f1 = tmp_path / "a.fits"
    f2 = tmp_path / "b.fits"
    _write_fits(f1, data)
    _write_fits(f2, data)

    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["detect", "--dry-run", str(f1), str(f2)])

    assert result.exit_code != 0
    assert "exactly one input file" in result.output


def test_c2_dry_run_zero_files_rejected(tmp_path):
    """wise detect --dry-run with zero files exits nonzero."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(cli, ["detect", "--dry-run"])

    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Hygiene #3: save_core_offset_pos_file ValueError
# ---------------------------------------------------------------------------

def test_hygiene3_save_core_offset_raises_valueerror_when_unset(tmp_path):
    """save_core_offset_pos_file raises ValueError when core_offset_filename is None."""
    ctx = wise.AnalysisContext()
    ctx.config.data.data_dir = str(tmp_path)
    ctx.config.data.core_offset_filename = None
    ctx.config.data.core_offset_fct = lambda c, img: None  # non-None so we pass the first guard

    with pytest.raises(ValueError, match="core_offset_filename"):
        ctx.save_core_offset_pos_file()


# ---------------------------------------------------------------------------
# Hygiene #4: get_stack_image raises RuntimeError
# ---------------------------------------------------------------------------

def test_hygiene4_get_stack_image_raises_runtimeerror(tmp_path):
    """get_stack_image raises RuntimeError (not bare Exception) when no file present."""
    ctx = wise.AnalysisContext()
    ctx.config.data.data_dir = str(tmp_path)
    # stack_image_filename default is 'full_stack_image.fits' — not present in tmp_path

    with pytest.raises(RuntimeError, match="wise stack"):
        ctx.get_stack_image()
