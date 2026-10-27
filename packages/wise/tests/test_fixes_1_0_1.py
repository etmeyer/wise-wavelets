"""Regression tests for the 1.0.1 bug fixes.

- Input selection: clear errors for missing files and when no file is usable
  (issue #12 follow-up: `wise show info` used to crash with an IndexError).
- Pixel grids: detect/match/stack refuse images on different grids instead of
  running silently, crashing on a numpy broadcast, or stacking garbage.
- `wise show info`: Bmaj before Bmin, PA in degrees, plain dates, and the
  unit only in the column header.
- astropy VerifyWarning (non-standard header cards) is silenced in the CLI.
- The finder widths footer and `wise detect --dry-run` match the real
  detection (intermediate scales, wavelet levels, ROI, mask).
- data.object_distance is an angular-diameter distance (its help text said
  luminosity distance, which overstates speeds by (1+z)^2 when object_z is
  also set).
"""
import datetime
import subprocess
import sys

import numpy as np
import pytest
from click.testing import CliRunner

pytest.importorskip("astropy")
fits = pytest.importorskip("astropy.io.fits")

import wise
from libwise import imgutils, nputils
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


# ---------------------------------------------------------------------------
# astropy VerifyWarning
# ---------------------------------------------------------------------------

def test_cli_silences_verify_warning_for_non_standard_cards(project):
    # astrogeo maps carry cards like this RA one, which astropy fixes on read
    # with a VerifyWarning. Run the real entry point: pytest records warnings
    # itself, so CliRunner output would never show them.
    path = _write_fits(project / "a.fits")
    fits.setval(path, "OBSERVER", value="PLACEHOLDER")
    raw = open(path, "rb").read()
    placeholder = "OBSERVER= 'PLACEHOLDER'".ljust(80).encode()
    assert placeholder in raw
    bad = "RA      = 13:04:59.069355 / Right ascension in HH:MM:SS.ssssss".ljust(80).encode()
    open(path, "wb").write(raw.replace(placeholder, bad))

    result = subprocess.run(
        [sys.executable, "-c", "from wise.cli import main; main()", "show", "info", path],
        cwd=project, capture_output=True, text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "a.fits" in result.stdout
    assert "VerifyWarning" not in result.stderr


# ---------------------------------------------------------------------------
# Finder widths footer and detect --dry-run
# ---------------------------------------------------------------------------

def test_widths_footer_includes_intermediate_scales(project):
    runner = CliRunner()
    runner.invoke(cli, ["settings", "set", "finder.min_scale=3", "finder.max_scale=6",
                        "finder.use_iwd=True"])

    result = runner.invoke(cli, ["settings", "show", "finder"])

    assert result.exit_code == 0, result.output
    assert "Resulting widths: [8, 12, 16, 24, 32, 48] px" in result.output


def _two_source_image(path):
    """64x64 px image with sources at x = 16 and x = 48 px (y = 32 px)."""
    _write_fits(path, shape=(64, 64))
    yy, xx = np.indices((64, 64))
    data = sum(np.exp(-((xx - x0) ** 2 + (yy - 32) ** 2) / (2 * 2.0 ** 2)) for x0 in (16, 48))
    data = data + np.random.default_rng(0).normal(0, 1e-3, data.shape)
    with fits.open(str(path), mode="update") as hdul:
        hdul[0].data = data.astype(np.float32)
    return str(path)


def _preview_context(**finder):
    """Settings that count only the two bright sources. The k-sigma noise
    estimate is randomised, so noise peaks near threshold come and go."""
    ctx = wise.AnalysisContext()
    ctx.config.data.bg_use_ksigma_method = True
    ctx.config.finder.set("alpha_detection", 20)
    for key, value in finder.items():
        ctx.config.finder.set(key, value)
    return ctx


def _n_above(ctx, path):
    return [s["n_above"] for s in wise.tasks.detection_preview(ctx, path)]


def test_dry_run_reports_wavelet_levels(project):
    path = _two_source_image(project / "src.fits")

    plain = wise.tasks.detection_preview(_preview_context(min_scale=1, max_scale=4), path)
    iwd = wise.tasks.detection_preview(
        _preview_context(min_scale=2, max_scale=4, use_iwd=True), path)

    assert [(s["level"], s["wavelet"]) for s in plain] == [(1, "b1"), (2, "b1"), (3, "b1")]
    assert [(s["level"], s["wavelet"], s["width"]) for s in iwd] == [
        (2, "b1", 4), (2, "b3", 6), (3, "b1", 8), (3, "b3", 12)]


def test_dry_run_ignores_peaks_outside_the_mask(project):
    path = _two_source_image(project / "src.fits")
    # Not "mask.fits", which is the default data.mask_filename.
    _write_fits(project / "east_half.fits", shape=(64, 64))
    with fits.open(str(project / "east_half.fits"), mode="update") as hdul:
        mask = np.zeros((64, 64), dtype=np.float32)
        mask[:, :32] = 1  # keeps the source at x = 16 px only
        hdul[0].data = mask
    ctx = _preview_context(min_scale=2, max_scale=4)

    assert _n_above(ctx, path) == [2, 2]
    ctx.config.data.mask_filename = "east_half.fits"
    assert _n_above(ctx, path) == [1, 1]


def test_dry_run_crops_to_the_roi(project):
    path = _two_source_image(project / "src.fits")
    ctx = _preview_context(min_scale=2, max_scale=4)

    assert _n_above(ctx, path) == [2, 2]
    # CDELT1 < 0, so the x = 16 px source is east (+576 mas) of the reference
    # pixel and the x = 48 px one is west (-576 mas). Keep the east half only.
    ctx.config.data.roi_coords = [1152.0, 1152.0, 0.0, -1152.0]
    assert _n_above(ctx, path) == [1, 1]


# ---------------------------------------------------------------------------
# Distances and proper velocities
# ---------------------------------------------------------------------------

def _proper_velocity_c(ctx, path):
    """Proper velocity (in c) of a 1-pixel shift per year."""
    import astropy.units as u
    prj = ctx.get_projection(imgutils.guess_and_open(path))
    return prj.proper_velocity([0, 0], [0, 1], 1 * u.year).to(wise.tasks.unit_c).value


def test_proper_velocity_is_angular_speed_times_da_times_1_plus_z(project):
    # The formula the data.object_distance / object_z help text documents.
    import astropy.constants as const
    import astropy.units as u
    from astropy.cosmology import WMAP9

    path = _write_fits(project / "a.fits", cdelt_deg=0.1 / 3.6e6)  # 0.1 mas pixels
    expected = ((0.1 * u.mas).to(u.rad).value / u.year
                * WMAP9.angular_diameter_distance(1.0) * 2 / const.c).decompose().value

    from_z = wise.AnalysisContext()
    from_z.config.data.object_z = 1.0
    explicit = wise.AnalysisContext()
    explicit.config.data.object_z = 1.0
    explicit.config.data.object_distance = WMAP9.angular_diameter_distance(1.0)

    assert _proper_velocity_c(from_z, path) == pytest.approx(expected, rel=1e-3)
    assert _proper_velocity_c(explicit, path) == pytest.approx(expected, rel=1e-3)
    assert expected == pytest.approx(5.32, abs=0.01)  # 53.2 c per mas/yr at z = 1
