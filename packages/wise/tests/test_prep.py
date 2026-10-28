"""Tests for `wise core`, `wise prep` (wise.prep) and sub-pixel core alignment.

The synthetic maps are built with an elliptical Gaussian written out here,
independently of wise.prep, so that a sign error in the beam position angle
or in the clean-component offsets can't cancel out.
"""
import datetime
import os

import numpy as np
import pytest
from click.testing import CliRunner

fits = pytest.importorskip("astropy.io.fits")

import wise
from libwise import imgutils
from wise import prep
from wise.cli import cli

MAS = 1 / 3.6e6  # in degrees
DEC = -21.11

# The seven astrogeo X-band beams of J1304-2106 (mas, mas, deg).
J1304_BEAMS = [(1.209, 0.712, -27.4), (3.311, 1.328, 0.2), (1.996, 0.761, -0.6),
               (2.503, 1.006, -6.9), (2.152, 0.834, -4.9), (1.985, 0.816, -0.4),
               (3.729, 0.938, -19.5)]


def _gaussian(x, y, x0, y0, bmaj, bmin, bpa):
    """Elliptical Gaussian of peak 1 whose major axis lies `bpa` degrees from
    north through east (x east, y north)."""
    t = np.radians(bpa)
    along = (x - x0) * np.sin(t) + (y - y0) * np.cos(t)
    across = (x - x0) * np.cos(t) - (y - y0) * np.sin(t)
    return np.exp(-4 * np.log(2) * ((along / bmaj) ** 2 + (across / bmin) ** 2))


def _write_map(path, components, n=128, pixel=0.1, beam=(1.0, 0.6, -20.0),
               date_obs="2020-01-01", noise=1e-4, seed=0, cc_table=True,
               crval=(196.25, DEC), freq_axes=False):
    """Write a VLBI-like map: point components (flux in Jy, x mas east and
    y mas north of the reference pixel) restored with `beam`, plus noise, and
    an AIPS CC table holding the components."""
    ref = n // 2
    xx, yy = np.meshgrid((np.arange(n) - ref) * -pixel, (np.arange(n) - ref) * pixel)
    data = sum(f * _gaussian(xx, yy, x0, y0, *beam) for f, x0, y0 in components)
    data = data + noise * np.random.default_rng(seed).standard_normal((n, n))
    hdu = fits.PrimaryHDU(data.astype(np.float32).reshape((1, 1, n, n) if freq_axes else (n, n)))
    h = hdu.header
    h["CTYPE1"], h["CRVAL1"], h["CDELT1"], h["CRPIX1"] = "RA---SIN", crval[0], -pixel * MAS, ref + 1
    h["CTYPE2"], h["CRVAL2"], h["CDELT2"], h["CRPIX2"] = "DEC--SIN", crval[1], pixel * MAS, ref + 1
    if freq_axes:
        h["CTYPE3"], h["CRVAL3"], h["CDELT3"], h["CRPIX3"] = "FREQ", 8.4e9, 1e6, 1.0
        h["CTYPE4"], h["CRVAL4"], h["CDELT4"], h["CRPIX4"] = "STOKES", 1.0, 1.0, 1.0
    h["BMAJ"], h["BMIN"], h["BPA"] = beam[0] * MAS, beam[1] * MAS, beam[2]
    h["DATE-OBS"] = date_obs
    h["OBJECT"] = "TEST"
    h["BUNIT"] = "JY/BEAM"
    hdus = [hdu]
    if cc_table:
        flux, x0, y0 = np.array(components, dtype=float).T
        hdus.append(fits.BinTableHDU.from_columns([
            fits.Column(name="FLUX", format="E", unit="JY", array=flux),
            fits.Column(name="DELTAX", format="E", unit="DEGREES", array=x0 * MAS),
            fits.Column(name="DELTAY", format="E", unit="DEGREES", array=y0 * MAS),
        ], name="AIPS CC"))
    fits.HDUList(hdus).writeto(str(path), overwrite=True)
    return str(path)


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A wise project root at tmp_path, with cwd set to it."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _context(files, **data_settings):
    config = wise.AnalysisConfiguration()
    for key, value in data_settings.items():
        setattr(config.data, key, value)
    ctx = wise.AnalysisContext(config)
    ctx.select_files([str(f) for f in files])
    return ctx


def _fit(path, data=None, **kwargs):
    m = prep.Map(_context([path]), str(path))
    if data is not None:
        m.data = data
    return prep.fit_core(m, **kwargs)


# Three epochs on different grids, with different beams, each core off the
# reference pixel by a fraction of a pixel, and a knot moving 0.5 mas/yr east.
MIXED = [  # n, pixel (mas), beam, DATE-OBS, core offset (mas)
    (256, 0.1, (1.2, 0.6, -10.0), "2020-01-01", (0.037, -0.052)),
    (128, 0.2, (1.6, 0.8, 35.0), "2021-01-01", (-0.163, 0.081)),
    (200, 0.125, (1.4, 0.7, -25.0), "2022-01-01", (0.24, 0.31)),
]


def _mixed_epochs(directory, cc_table=True):
    paths = []
    for k, (n, pixel, beam, date_obs, (x0, y0)) in enumerate(MIXED):
        components = [(1.0, x0, y0), (0.3, x0 + 3.0 + 0.5 * k, y0 + 0.5)]
        paths.append(_write_map(directory / ("X_%d.fits" % k), components, n=n, pixel=pixel,
                                beam=beam, date_obs=date_obs, seed=k, cc_table=cc_table))
    return paths


def _prep(*args):
    result = CliRunner().invoke(cli, ["prep", *args])
    return result


# ---------------------------------------------------------------------------
# Beams
# ---------------------------------------------------------------------------

def test_beam_position_angle_is_east_of_north():
    north = prep.Beam(2.0, 1.0, 0.0).cov()
    east = prep.Beam(2.0, 1.0, 90.0).cov()

    assert (north[0, 0], north[1, 1]) == pytest.approx((1.0, 4.0))
    assert (east[0, 0], east[1, 1]) == pytest.approx((4.0, 1.0))
    b = prep.Beam.from_cov(prep.Beam(2.0, 1.0, 30.0).cov())
    assert (b.bmaj, b.bmin, b.bpa) == pytest.approx((2.0, 1.0, 30.0))


def test_common_beam_of_identical_beams_is_that_beam():
    c = prep.common_beam([prep.Beam(1.5, 0.7, -25.0)] * 3)

    assert (c.bmaj, c.bmin, c.bpa) == pytest.approx((1.5, 0.7, -25.0), abs=1e-4)


def test_common_beam_of_crossed_beams_is_round():
    c = prep.common_beam([prep.Beam(2.0, 1.0, 0.0), prep.Beam(2.0, 1.0, 90.0)])

    assert (c.bmaj, c.bmin) == pytest.approx((2.0, 2.0), rel=1e-4)


def _smallest_containing_area(beams):
    # Brute force over a grid of candidate beams; 2x2 C - B is positive
    # semi-definite when both diagonal terms and the determinant are >= 0.
    t = np.radians(np.arange(-90, 90, 0.5))[:, None, None]
    a = np.linspace(1, 5, 201)[None, :, None]
    b = np.linspace(0.5, 5, 226)[None, None, :]
    cxx = a ** 2 * np.sin(t) ** 2 + b ** 2 * np.cos(t) ** 2
    cyy = a ** 2 * np.cos(t) ** 2 + b ** 2 * np.sin(t) ** 2
    cxy = (a ** 2 - b ** 2) * np.sin(t) * np.cos(t)
    ok = np.ones(np.broadcast(t, a, b).shape, dtype=bool)
    for beam in beams:
        (bxx, bxy), (_, byy) = beam.cov()
        dxx, dyy, dxy = cxx - bxx, cyy - byy, cxy - bxy
        ok &= (dxx >= 0) & (dyy >= 0) & (dxx * dyy - dxy ** 2 >= 0)
    return np.where(ok, a * b, np.inf).min()


@pytest.mark.parametrize("beams", [
    [prep.Beam(*b) for b in J1304_BEAMS],
    [prep.Beam(2.4, 0.9, 70.0), prep.Beam(1.8, 1.1, -15.0), prep.Beam(2.0, 0.6, 20.0)],
])
def test_common_beam_is_the_smallest_beam_containing_all(beams):
    c = prep.common_beam(beams)

    assert all(c.contains(b) for b in beams)
    assert c.bmaj * c.bmin <= _smallest_containing_area(beams) * (1 + 1e-6)


def test_common_beam_of_the_j1304_epochs():
    # The J1304 prototype's grid search found 4.15 x 1.56 mas at PA -10; the
    # area changes slowly with PA near its minimum.
    c = prep.common_beam([prep.Beam(*b) for b in J1304_BEAMS])

    assert (c.bmaj, c.bmin) == pytest.approx((4.15, 1.56), abs=0.01)
    assert c.bpa == pytest.approx(-10.0, abs=0.1)


# ---------------------------------------------------------------------------
# Restoring clean components
# ---------------------------------------------------------------------------

def test_restore_matches_a_direct_sum():
    rng = np.random.default_rng(2)
    cc = np.zeros((60, 6))
    cc[:, 0] = rng.uniform(-0.01, 0.1, 60)
    cc[:, 1:3] = rng.uniform(-3, 3, (60, 2))
    cc[:10, 1:3] = cc[10:20, 1:3]  # components at the same position
    x, y = (np.arange(81) - 40) * -0.1, (np.arange(81) - 40) * 0.1
    xx, yy = np.meshgrid(x, y)
    expected = sum(f * _gaussian(xx, yy, x0, y0, 1.2, 0.5, 35.0) for f, x0, y0 in cc[:, :3])

    out = prep.restore(cc, x, y, prep.Beam(1.2, 0.5, 35.0))

    assert np.abs(out - expected).max() < 1e-5 * np.abs(cc[:, 0]).sum()


def test_restore_gaussian_component():
    # A Gaussian component restored with a beam of the same PA: the widths
    # add in quadrature, and the peak drops so that the flux is kept.
    cc = np.array([[1.0, 0.2, -0.1, 0.8, 0.3, 35.0]])
    x, y = (np.arange(81) - 40) * -0.1, (np.arange(81) - 40) * 0.1
    xx, yy = np.meshgrid(x, y)
    bmaj, bmin = np.hypot(1.2, 0.8), np.hypot(0.5, 0.3)
    expected = 1.2 * 0.5 / (bmaj * bmin) * _gaussian(xx, yy, 0.2, -0.1, bmaj, bmin, 35.0)

    out = prep.restore(cc, x, y, prep.Beam(1.2, 0.5, 35.0))

    assert np.abs(out - expected).max() < 1e-5


# ---------------------------------------------------------------------------
# Core fits
# ---------------------------------------------------------------------------

def test_fit_core_recovers_a_subpixel_offset(project):
    path = _write_map(project / "a.fits", [(1.0, 0.037, -0.052), (0.2, 3.0, 0.5)])

    fit = _fit(path)

    assert (fit.x, fit.y) == pytest.approx((0.037, -0.052), abs=0.002)
    assert 0 < fit.x_err < 0.01 and 0 < fit.y_err < 0.01
    assert fit.snr > 1000
    # A point-like core: the free-shape fit finds the beam.
    assert (fit.free.bmaj, fit.free.bmin, fit.free.bpa) == pytest.approx((1.0, 0.6, -20.0), rel=0.03)


def test_fit_core_looks_near_the_reference_pixel(project):
    # A jet knot brighter than the core, 4 mas east of it.
    path = _write_map(project / "a.fits", [(0.5, 0.0, 0.0), (1.0, 4.0, 0.0)])

    assert _fit(path).x == pytest.approx(0.0, abs=0.002)
    assert _fit(path, near=(4.0, 0.0)).x == pytest.approx(4.0, abs=0.002)
    assert _fit(path, search_radius=5.0).x == pytest.approx(4.0, abs=0.002)


# ---------------------------------------------------------------------------
# wise core and alignment
# ---------------------------------------------------------------------------

# Each away from half a pixel, so that rounding to whole pixels is unambiguous.
SAME_GRID_CORES = [(0.037, -0.062), (-0.163, 0.081), (0.24, 0.31)]


def _same_grid_epochs(directory):
    return [_write_map(directory / ("X_%d.fits" % k), [(1.0, x0, y0), (0.3, x0 + 3, y0 + 0.5)],
                       date_obs="%d-01-01" % (2020 + k), seed=k)
            for k, (x0, y0) in enumerate(SAME_GRID_CORES)]


def test_wise_core_writes_the_core_offset_file(project):
    paths = _same_grid_epochs(project)

    result = CliRunner().invoke(cli, ["core", *paths])

    assert result.exit_code == 0, result.output
    assert "Core offsets written to" in result.output
    cores = wise.CoreOffsetPositions.new_from_file(str(project / "core.dat"))
    for k, xy in enumerate(SAME_GRID_CORES):
        assert cores.get(datetime.datetime(2020 + k, 1, 1)) == pytest.approx(xy, abs=0.002)


def test_wise_core_dry_run_and_overwrite(project):
    paths = _same_grid_epochs(project)

    assert CliRunner().invoke(cli, ["core", "--dry-run", *paths]).exit_code == 0
    assert not (project / "core.dat").exists()
    assert CliRunner().invoke(cli, ["core", *paths]).exit_code == 0
    result = CliRunner().invoke(cli, ["core", *paths])
    assert result.exit_code == 2 and "--overwrite" in result.output
    assert CliRunner().invoke(cli, ["core", "--overwrite", "-o", "other.dat", *paths]).exit_code == 0
    assert (project / "other.dat").exists()


@pytest.mark.parametrize("subpixel", [True, False])
def test_alignment_on_wise_core_offsets(project, subpixel):
    paths = _same_grid_epochs(project)
    assert CliRunner().invoke(cli, ["core", *paths]).exit_code == 0
    ctx = _context(paths, align_subpixel=subpixel)

    for path, (x0, y0) in zip(paths, SAME_GRID_CORES):
        img = ctx.open_file(path)
        ctx.align(img)
        fit = _fit(path, data=img.data)
        if subpixel:
            # Within 0.03 pixel of the reference pixel.
            assert np.hypot(fit.x, fit.y) < 0.003
        else:
            # Whole-pixel shifts, as in wise 1.0, leave the fractional part.
            rest = (x0 - 0.1 * round(x0 / 0.1), y0 - 0.1 * round(y0 / 0.1))
            assert (fit.x, fit.y) == pytest.approx(rest, abs=0.003)


def test_alignment_leaves_maps_centered_by_wise_prep(project):
    # A core offset file measured on the input maps, in the same project.
    paths = _same_grid_epochs(project)
    assert CliRunner().invoke(cli, ["core", *paths]).exit_code == 0
    assert _prep(*paths, "-o", "centered").exit_code == 0
    assert _prep(*paths, "-o", "regridded", "--no-center").exit_code == 0

    for directory, shifted in (("centered", False), ("regridded", True)):
        path = str(project / directory / os.path.basename(paths[0]))
        assert fits.getheader(path)["PREP_CEN"] == (not shifted)
        ctx = _context([path])
        img = ctx.open_file(path)
        before = img.data.copy()
        ctx.align(img)
        assert np.array_equal(img.data, before) == (not shifted)


def test_align_subpixel_is_the_default():
    assert wise.AnalysisConfiguration().data.align_subpixel is True


def test_core_offsets_match_epochs_by_day(project):
    # A single-row file, and an image epoch with a time of day.
    (project / "core.dat").write_text("2020-01-01 0 0.1 90\n")

    cores = wise.CoreOffsetPositions.new_from_file(str(project / "core.dat"))

    assert cores.get(datetime.datetime(2020, 1, 1, 13, 45)) == pytest.approx([0.1, 0.0])


# ---------------------------------------------------------------------------
# wise prep
# ---------------------------------------------------------------------------

def test_wise_prep_puts_mixed_grids_on_one_grid_with_cores_centered(project):
    paths = _mixed_epochs(project)

    result = _prep(*paths, "-o", "prep")

    assert result.exit_code == 0, result.output
    # The finest pixel (0.1 mas) over the smallest field (200 x 0.125 = 25 mas).
    assert "250 x 250 px at 0.1 mas" in result.output
    assert (project / "prep" / prep.LOG_FILENAME).exists()
    out = [str(project / "prep" / os.path.basename(p)) for p in paths]
    ctx = _context(out)
    ctx.check_common_grid()
    for k, (path, (n, pixel, beam, date_obs, (x0, y0))) in enumerate(zip(out, MIXED)):
        h = fits.getheader(path)
        assert (h["NAXIS1"], h["NAXIS2"], h["CRPIX1"], h["CRPIX2"]) == (250, 250, 126, 126)
        assert h["CDELT2"] / MAS == pytest.approx(0.1)
        assert (h["BMAJ"] / MAS, h["BMIN"] / MAS, h["BPA"]) == pytest.approx(beam)
        assert h["DATE-OBS"] == date_obs
        assert h["ORIGFILE"] == os.path.basename(path)
        # The reference pixel is now at the core's sky position.
        cos_dec = np.cos(np.radians(DEC))
        assert h["CRVAL1"] == pytest.approx(196.25 + x0 * MAS / cos_dec, abs=0.003 * MAS / cos_dec)
        assert h["CRVAL2"] == pytest.approx(DEC + y0 * MAS, abs=0.003 * MAS)
        core = _fit(path)
        assert np.hypot(core.x, core.y) < 0.003
        assert core.peak == pytest.approx(1.0, abs=0.005)
        # The knot keeps its position relative to the core, and its flux.
        knot = _fit(path, near=(3.0 + 0.5 * k, 0.5), search_radius=0.4)
        assert (knot.x, knot.y) == pytest.approx((3.0 + 0.5 * k, 0.5), abs=0.003)
        assert knot.peak == pytest.approx(0.3, abs=0.005)


def test_wise_prep_common_beam(project):
    paths = _mixed_epochs(project)
    common = prep.common_beam([prep.Beam(*spec[2]) for spec in MIXED])

    result = _prep(*paths, "-o", "prep", "--beam", "common")

    assert result.exit_code == 0, result.output
    assert str(common) in result.output
    for path in paths:
        out = str(project / "prep" / os.path.basename(path))
        h = fits.getheader(out)
        assert (h["BMAJ"] / MAS, h["BMIN"] / MAS, h["BPA"]) == pytest.approx(
            (common.bmaj, common.bmin, common.bpa))
        core = _fit(out)
        # Jy/beam: a point source's peak is its flux, whatever the beam.
        assert core.peak == pytest.approx(1.0, abs=0.005)
        assert (core.free.bmaj, core.free.bmin) == pytest.approx((common.bmaj, common.bmin), rel=0.02)
        assert core.free.bpa == pytest.approx(common.bpa, abs=1)


def test_wise_prep_without_clean_components(project):
    paths = _mixed_epochs(project, cc_table=False)
    common = prep.common_beam([prep.Beam(*spec[2]) for spec in MIXED])

    native = _prep(*paths, "-o", "native")
    convolved = _prep(*paths, "-o", "common", "--beam", "common")

    assert native.exit_code == 0, native.output
    assert convolved.exit_code == 0, convolved.output
    assert "interpolated, convolved" in convolved.output
    for path in paths:
        core = _fit(project / "native" / os.path.basename(path))
        assert np.hypot(core.x, core.y) < 0.003
        assert core.peak == pytest.approx(1.0, abs=0.01)
        # The convolution gives the common beam, including its orientation,
        # and the change of units keeps a point source's peak at its flux.
        core = _fit(project / "common" / os.path.basename(path))
        assert np.hypot(core.x, core.y) < 0.003
        assert core.peak == pytest.approx(1.0, abs=0.01)
        assert (core.free.bmaj, core.free.bmin) == pytest.approx((common.bmaj, common.bmin), rel=0.02)
        assert core.free.bpa == pytest.approx(common.bpa, abs=1)


def test_wise_prep_without_clean_components_needs_a_containing_beam(project):
    paths = _mixed_epochs(project, cc_table=False)

    result = _prep(*paths, "-o", "prep", "--beam", "1.0,0.5,0")

    assert result.exit_code == 1
    assert "has no clean components" in result.output
    assert not (project / "prep").exists()


def test_wise_prep_no_center_lines_maps_up_on_the_sky(project):
    # b's phase centre is 1 mas east and 0.5 mas south of a's; the source sits
    # at a's phase centre in both.
    a = _write_map(project / "a.fits", [(1.0, 0.0, 0.0)], date_obs="2020-01-01")
    b = _write_map(project / "b.fits", [(1.0, -1.0, 0.5)], date_obs="2021-01-01",
                   crval=(196.25 + MAS / np.cos(np.radians(DEC)), DEC - 0.5 * MAS))

    result = _prep(a, b, "-o", "prep", "--no-center")

    assert result.exit_code == 0, result.output
    for name in ("a.fits", "b.fits"):
        path = project / "prep" / name
        fit = _fit(path)
        assert np.hypot(fit.x, fit.y) < 0.003
        h = fits.getheader(path)
        assert (h["CRVAL1"], h["CRVAL2"]) == pytest.approx((196.25, DEC), abs=1e-12)


def test_wise_prep_keeps_frequency_and_stokes_axes(project):
    path = _write_map(project / "a.fits", [(1.0, 0.0, 0.0)], freq_axes=True)

    assert _prep(path, "-o", "prep").exit_code == 0

    h = fits.getheader(project / "prep" / "a.fits")
    assert (h["NAXIS"], h["CTYPE3"], h["CTYPE4"]) == (4, "FREQ", "STOKES")
    assert imgutils.FitsImage(str(project / "prep" / "a.fits")).get_frequency() == 8.4e9


def test_wise_prep_never_overwrites_inputs(project):
    paths = _mixed_epochs(project)

    result = _prep(*paths, "-o", str(project))

    assert result.exit_code == 1
    assert "would overwrite its input" in result.output


def test_wise_prep_replaces_outputs_only_with_overwrite(project):
    paths = _mixed_epochs(project)
    assert _prep(*paths, "-o", "prep").exit_code == 0

    again = _prep(*paths, "-o", "prep")

    assert again.exit_code == 1 and "--overwrite" in again.output
    assert _prep(*paths, "-o", "prep", "--overwrite").exit_code == 0


def test_wise_prep_rejects_a_bad_beam(project):
    paths = _mixed_epochs(project)

    for beam in ("1,2", "0.5,1.0,0", "wide"):
        result = _prep(*paths, "-o", "prep", "--beam", beam)
        assert result.exit_code == 2, (beam, result.output)
