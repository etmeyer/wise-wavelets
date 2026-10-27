"""Regression tests for the 1.0.1 bug fixes.

- Input selection: clear errors for missing files and when no file is usable
  (issue #12 follow-up: `wise show info` used to crash with an IndexError).
- Pixel grids: detect/match/stack refuse images on different grids instead of
  running silently, crashing on a numpy broadcast, or stacking garbage.
- `wise show info`: Bmaj before Bmin, PA in degrees, plain dates, and the
  unit only in the column header.
"""
import datetime

import numpy as np
import pytest
from click.testing import CliRunner

pytest.importorskip("astropy")
fits = pytest.importorskip("astropy.io.fits")

from libwise import imgutils, nputils

import wise
from wise.cli import cli


def _write_fits(path, shape=(32, 32), cdelt_deg=1e-5, date_obs="2026-01-01"):
    """Write a minimal 2D FITS image with a SIN projection and a beam."""
    hdu = fits.PrimaryHDU(np.zeros(shape, dtype=np.float32))
    hdu.header["DATE-OBS"] = date_obs
    hdu.header["BMAJ"] = 3 * cdelt_deg
    hdu.header["BMIN"] = 2 * cdelt_deg
    hdu.header["BPA"] = -20.0
    hdu.header["CRVAL1"] = 0.0
    hdu.header["CRVAL2"] = 0.0
    hdu.header["CRPIX1"] = shape[1] / 2 + 1
    hdu.header["CRPIX2"] = shape[0] / 2 + 1
    hdu.header["CDELT1"] = -cdelt_deg
    hdu.header["CDELT2"] = cdelt_deg
    hdu.header["CTYPE1"] = "RA---SIN"
    hdu.header["CTYPE2"] = "DEC--SIN"
    hdu.writeto(str(path), overwrite=True)
    return str(path)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A wise project root at tmp_path, with cwd set to it."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Input selection
# ---------------------------------------------------------------------------

def test_show_info_missing_file_is_a_usage_error(project):
    result = CliRunner().invoke(cli, ["show", "info", "X_*.fits"])

    assert result.exit_code == 2, result.output
    assert "File not found: X_*.fits" in result.output
    assert "Traceback" not in result.output


def test_show_info_with_no_usable_file_is_a_usage_error(project):
    # Issue #12: a single file whose DATE-OBS can't be parsed used to end in
    # an IndexError from format_table.
    bad = _write_fits(project / "bad.fits", date_obs="not a date")

    result = CliRunner().invoke(cli, ["show", "info", bad])

    assert result.exit_code == 2, result.output
    assert "No usable input files (1 skipped" in result.output
    assert not isinstance(result.exception, IndexError)


def test_file_list_input_ignores_blank_lines(project):
    img = _write_fits(project / "a.fits")
    (project / "files").write_text(img + "\n\n")

    result = CliRunner().invoke(cli, ["show", "info", "files"])

    assert result.exit_code == 0, result.output
    assert "a.fits" in result.output


def test_format_table_with_no_rows():
    assert nputils.format_table([]) == ""
    table = nputils.format_table([], ["File", "Date"])
    assert "File" in table and "Date" in table


# ---------------------------------------------------------------------------
# Pixel grids
# ---------------------------------------------------------------------------

def test_detect_refuses_mixed_pixel_scales(project):
    a = _write_fits(project / "a.fits", cdelt_deg=1e-5, date_obs="2026-01-01")
    b = _write_fits(project / "b.fits", cdelt_deg=2e-5, date_obs="2026-02-01")

    result = CliRunner().invoke(cli, ["-q", "--non-interactive", "detect", a, b, "--no-save"])

    assert result.exit_code == 1, result.output
    assert "not on one pixel grid" in result.output
    assert "32x32 px at 36 mas/px: a.fits" in result.output
    assert "32x32 px at 72 mas/px: b.fits" in result.output


def test_stack_refuses_mixed_shapes(project):
    a = _write_fits(project / "a.fits", shape=(32, 32), date_obs="2026-01-01")
    b = _write_fits(project / "b.fits", shape=(16, 16), date_obs="2026-02-01")

    result = CliRunner().invoke(cli, ["-q", "stack", a, b, "-o", "stack.fits"])

    assert result.exit_code == 1, result.output
    assert "not on one pixel grid" in result.output
    assert "Image shape are not adequate" not in result.output
    assert not (project / "stack.fits").exists()


def test_check_common_grid_accepts_one_grid(project):
    ctx = wise.AnalysisContext()
    ctx.select_files([_write_fits(project / "a.fits", date_obs="2026-01-01"),
                      _write_fits(project / "b.fits", date_obs="2026-02-01")])

    ctx.check_common_grid()


def test_check_common_grid_includes_the_reference_image(project):
    ctx = wise.AnalysisContext()
    ctx.select_files([_write_fits(project / "a.fits", date_obs="2026-01-01"),
                      _write_fits(project / "b.fits", date_obs="2026-02-01")])
    _write_fits(project / "ref.fits", cdelt_deg=2e-5)
    ctx.config.data.ref_image_filename = "ref.fits"

    with pytest.raises(wise.GridMismatchError, match=r"ref\.fits \(reference image\)"):
        ctx.check_common_grid()
    # Building a stack (which often replaces the reference image) skips it.
    ctx.check_common_grid(include_ref=False)


# ---------------------------------------------------------------------------
# show info display
# ---------------------------------------------------------------------------

def test_get_epoch_formats_datetimes():
    img = imgutils.Image(np.zeros((2, 2)), epoch=datetime.datetime(2015, 9, 28))

    assert img.get_epoch(str_format="%Y-%m-%d") == "2015-09-28"
    assert img.get_epoch() == datetime.datetime(2015, 9, 28)


def test_show_info_lists_bmaj_first_with_pa_in_degrees(project):
    # 36 mas pixels; beam 3 x 2 px at BPA -20 deg.
    img = _write_fits(project / "a.fits")

    result = CliRunner().invoke(cli, ["show", "info", img])

    assert result.exit_code == 0, result.output
    assert "2026-01-01 " in result.output
    assert "00:00:00" not in result.output
    assert "108.000 x 72.000, -20.0" in result.output
    assert "36.000 mas" not in result.output
    assert "Mean beam: 108.000 x 72.000 mas, PA -20.0 deg" in result.output


def test_show_info_velocity_prints_dates(project):
    a = _write_fits(project / "a.fits", date_obs="2026-01-01")
    b = _write_fits(project / "b.fits", date_obs="2026-02-01")

    result = CliRunner().invoke(cli, ["show", "info", "--velocity", a, b])

    assert result.exit_code == 0, result.output
    assert "Images have no date information" not in result.output
    assert "2026-01-01 |2026-02-01 |31.0" in result.output
