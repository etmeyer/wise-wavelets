"""Images from the same day are refused before any work by every step that
combines epochs (detect, match, bootstrap matching, stack, wise core and
wise prep): detections, core offsets and velocities are per date, and the
core offset file holds one position per day.
"""
import numpy as np
import pytest
from click.testing import CliRunner

fits = pytest.importorskip("astropy.io.fits")

import wise
from wise import tasks
from wise.cli import cli


def _write_fits(path, date_obs):
    """Write an empty 32 x 32 map with a beam."""
    hdu = fits.PrimaryHDU(np.zeros((32, 32), dtype=np.float32))
    h = hdu.header
    h["DATE-OBS"] = date_obs
    h["CTYPE1"], h["CRVAL1"], h["CDELT1"], h["CRPIX1"] = "RA---SIN", 0.0, -1e-7, 17
    h["CTYPE2"], h["CRVAL2"], h["CDELT2"], h["CRPIX2"] = "DEC--SIN", 0.0, 1e-7, 17
    h["BMAJ"], h["BMIN"], h["BPA"] = 4e-7, 3e-7, 0.0
    path.parent.mkdir(parents=True, exist_ok=True)
    hdu.writeto(str(path))
    return str(path)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A wise project root at tmp_path, with cwd set to it."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _context(*paths):
    ctx = wise.AnalysisContext()
    ctx.select_files(list(paths))
    return ctx


def test_images_from_different_days_pass(project):
    ctx = _context(_write_fits(project / "a.fits", "2026-01-01"),
                   _write_fits(project / "b.fits", "2026-01-02"))

    ctx.check_unique_epochs()


@pytest.mark.parametrize("date_b, date_c", [
    ("2026-02-01", "2026-02-01"),
    # Hours apart: too little time to measure a motion, and one row in a
    # core offset file.
    ("2026-02-01T03:00:00", "2026-02-01T21:00:00"),
    # astrogeo's counter for a second observation on the same day.
    ("2026-02-01", "2026-02-01(2)"),
])
def test_images_from_the_same_day_are_listed(project, date_b, date_c):
    ctx = _context(_write_fits(project / "a.fits", "2026-01-01"),
                   _write_fits(project / "b.fits", date_b),
                   _write_fits(project / "c.fits", date_c))

    with pytest.raises(wise.DuplicateEpochError) as error:
        ctx.check_unique_epochs()

    assert "2026-02-01: b.fits, c.fits" in str(error.value)
    assert "a.fits" not in str(error.value)


def test_same_names_from_different_directories_are_shown_as_paths(project):
    ctx = _context(_write_fits(project / "raw" / "a.fits", "2026-01-01"),
                   _write_fits(project / "prep" / "a.fits", "2026-01-01"))

    with pytest.raises(wise.DuplicateEpochError, match=r"raw/a\.fits, .*prep/a\.fits"):
        ctx.check_unique_epochs()


@pytest.mark.parametrize("run", [
    tasks.detection_all,
    tasks.match_all,
    tasks.bootstrap_matching,
    lambda ctx: ctx.build_stack_image(),
    wise.prep.measure_cores,
    lambda ctx: wise.prep.prepare_files(ctx, "prep"),
], ids=["detection_all", "match_all", "bootstrap_matching", "build_stack_image",
        "measure_cores", "prepare_files"])
def test_steps_that_combine_epochs_check_them_first(project, run):
    # Without the check, each of these fails differently on empty maps, or
    # (stacking) not at all.
    ctx = _context(_write_fits(project / "a.fits", "2026-01-01"),
                   _write_fits(project / "b.fits", "2026-01-01"))

    with pytest.raises(wise.DuplicateEpochError):
        run(ctx)
    assert not (project / "prep").exists()


@pytest.mark.parametrize("args", [
    ["--non-interactive", "detect", "--no-save"],
    ["--non-interactive", "match", "--no-save"],
    ["stack", "-o", "stack.fits"],
    ["core"],
    ["prep", "-o", "prep"],
])
def test_commands_stop_with_the_list_of_images(project, args):
    a = _write_fits(project / "a.fits", "2026-01-01")
    b = _write_fits(project / "b.fits", "2026-01-01")

    result = CliRunner().invoke(cli, ["-q", *args, a, b])

    assert result.exit_code == 1, result.output
    assert "observed on the same day" in result.output
    assert "2026-01-01: a.fits, b.fits" in result.output
    assert not any((project / name).exists() for name in ("stack.fits", "core.dat", "prep"))
