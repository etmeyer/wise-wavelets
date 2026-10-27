"""Prepare multi-epoch VLBI maps for wise.

- :func:`fit_core` measures the position of a map's core.
- :func:`prepare_map` resamples a map onto a common :class:`Grid` with a
  chosen sky position (normally the core) on the reference pixel, keeping
  the map's own beam or restoring it with another one.

``wise core`` and ``wise prep`` are the command-line front ends
(:func:`measure_cores`, :func:`write_core_file`, :func:`prepare_files`).

Positions are offsets in mas from a map's reference pixel, x positive to
the east and y to the north. Beam position angles are in degrees east of
north.
"""
import dataclasses
import datetime
import logging
import os

import astropy.units as u
import click
import numpy as np
from astropy.io import fits
from libwise import imgutils, nputils
from scipy import ndimage, optimize

import wise

from . import wiseutils

logger = logging.getLogger(__name__)

MAS_PER_DEG = 3.6e6
# exp(-FOUR_LN2 * d**2 / fwhm**2) is a Gaussian of full width fwhm at half maximum.
FOUR_LN2 = 4 * np.log(2)
# Gaussians are evaluated out to this many sigma.
N_SIGMA = 5
LOG_FILENAME = "prep_log.txt"


class PrepError(click.ClickException):
    """Raised when a map can't be measured or prepared."""


def _cov(bmaj, bmin, bpa):
    # FWHM^2 covariance in (x east, y north) of an ellipse with the given axes.
    t = np.radians(bpa)
    major = np.array([np.sin(t), np.cos(t)])
    minor = np.array([np.cos(t), -np.sin(t)])
    return bmaj ** 2 * np.outer(major, major) + bmin ** 2 * np.outer(minor, minor)


@dataclasses.dataclass(frozen=True)
class Beam:
    """Elliptical Gaussian beam: full widths at half maximum in mas, position
    angle of the major axis in degrees east of north."""

    bmaj: float
    bmin: float
    bpa: float

    def __str__(self):
        return "%.3f x %.3f mas, PA %.1f deg" % (self.bmaj, self.bmin, self.bpa)

    def cov(self):
        """FWHM^2 covariance matrix in (x east, y north), mas^2."""
        return _cov(self.bmaj, self.bmin, self.bpa)

    @staticmethod
    def from_cov(cov):
        evals, evecs = np.linalg.eigh(cov)
        major = evecs[:, 1]
        pa = (np.degrees(np.arctan2(major[0], major[1])) + 90) % 180 - 90
        return Beam(float(np.sqrt(evals[1])), float(np.sqrt(max(evals[0], 0))), float(pa))

    def area(self):
        """Solid angle, mas^2."""
        return np.pi / FOUR_LN2 * self.bmaj * self.bmin

    def contains(self, other, rtol=1e-6):
        """True if this beam is at least as wide as `other` in every direction."""
        return np.linalg.eigvalsh(self.cov() - other.cov()).min() >= -rtol * self.bmaj ** 2


def common_beam(beams):
    """Return the smallest-area beam that contains every beam in `beams`."""
    covs = np.array([b.cov() for b in beams])

    def best_for_pa(pa):
        # In axes along (u) and across (v) a candidate major axis at `pa`, the
        # beam diag(A, B) contains a beam [[p, r], [r, q]] when A >= p and
        # B >= q + r^2 / (A - p). Minimize the area, A * B, over A.
        t = np.radians(pa)
        rot = np.array([[np.sin(t), np.cos(t)], [np.cos(t), -np.sin(t)]])
        c = rot @ covs @ rot.T
        p, q, r2 = c[:, 0, 0], c[:, 1, 1], c[:, 0, 1] ** 2

        def minor2(a2):
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.max(q + np.where(r2 > 0, r2 / (a2 - p), 0))

        a0 = p.max()
        a2s = a0 * (1 + np.concatenate([[0], np.geomspace(1e-9, 20, 400)]))
        areas = [a2 * minor2(a2) for a2 in a2s]
        k = int(np.argmin(areas))
        if 0 < k < len(a2s) - 1:
            res = optimize.minimize_scalar(lambda a2: a2 * minor2(a2), bounds=(a2s[k - 1], a2s[k + 1]),
                                           method="bounded", options={"xatol": a0 * 1e-12})
            if res.fun < areas[k]:
                return res.fun, res.x, minor2(res.x)
        return areas[k], a2s[k], minor2(a2s[k])

    step = 0.5
    pas = np.arange(-90, 90, step)
    k = int(np.argmin([best_for_pa(pa)[0] for pa in pas]))
    res = optimize.minimize_scalar(lambda pa: best_for_pa(pa)[0], bounds=(pas[k] - step, pas[k] + step),
                                   method="bounded", options={"xatol": 1e-4})
    pa = res.x if res.fun < best_for_pa(pas[k])[0] else pas[k]
    _, a2, b2 = best_for_pa(pa)
    # A hair larger, so that containment survives rounding.
    beam = Beam.from_cov(_cov(np.sqrt(a2), np.sqrt(b2), pa) * (1 + 1e-6))
    assert all(beam.contains(b) for b in beams)
    return beam


class Map:
    """A FITS map with what wise prep needs: data, pixel grid, beam and clean
    components (``cc``: N x 6, flux in Jy, then positions, axes in mas and PA
    in degrees, or None)."""

    def __init__(self, ctx, path):
        img = ctx.open_file(path)
        if not isinstance(img, imgutils.FitsImage):
            raise PrepError("%s is not a FITS image." % path)
        pc = img.wcs.wcs.get_pc()
        if abs(pc[0, 1]) > 1e-9 or abs(pc[1, 0]) > 1e-9:
            raise PrepError("%s: rotated pixel grids are not supported." % path)
        if img.beam_data is None:
            raise PrepError("%s has no restoring beam (BMAJ, BMIN, BPA)." % path)
        self.path = path
        self.image = img
        self.epoch = img.get_epoch()
        self.data = img.data
        prj = img.get_projection(relative=True, center="pix_ref", unit=u.mas)
        # mas per pixel; x is negative when RA increases to the left.
        self.scales = np.asarray(prj.pixel_scales(), dtype=float)
        self.pix_ref = np.asarray(img.get_pix_ref(), dtype=float)
        self.crval = np.array(img.wcs.wcs.crval, dtype=float)
        bmaj, bmin, bpa = img.beam_data
        self.beam = Beam(bmaj * MAS_PER_DEG, bmin * MAS_PER_DEG, bpa)
        self.cc = img.get_clean_components()
        if self.cc is not None:
            self.cc[:, 1:5] *= MAS_PER_DEG

    def axes(self):
        """Offsets (mas) of the pixel centres from the reference pixel, along x and y."""
        ny, nx = self.data.shape
        return ((np.arange(nx) - self.pix_ref[0]) * self.scales[0],
                (np.arange(ny) - self.pix_ref[1]) * self.scales[1])

    def name(self):
        return os.path.basename(self.path)


def noise_rms(data):
    """Robust noise level: the scaled MAD of the four corners, or of the whole
    map if the corners are empty."""
    ny, nx = data.shape
    by, bx = max(ny // 8, 8), max(nx // 8, 8)
    corners = np.concatenate([data[:by, :bx].ravel(), data[:by, -bx:].ravel(),
                              data[-by:, :bx].ravel(), data[-by:, -bx:].ravel()])
    for values in (corners, data.ravel()):
        values = values[np.isfinite(values)]
        if values.size:
            rms = 1.4826 * np.median(np.abs(values - np.median(values)))
            if rms > 0:
                return rms
    return np.nan


def _gauss(x, y, x0, y0, cov_inv):
    dx, dy = x - x0, y - y0
    q = cov_inv[0, 0] * dx ** 2 + 2 * cov_inv[0, 1] * dx * dy + cov_inv[1, 1] * dy ** 2
    return np.exp(-FOUR_LN2 * q)


@dataclasses.dataclass
class CoreFit:
    """Core position (mas from the reference pixel) from a fit of a Gaussian
    with the restoring-beam shape. ``free`` is the shape found when the size
    and PA are fitted too, as a check for a resolved or blended core."""

    x: float
    y: float
    x_err: float
    y_err: float
    peak: float
    rms: float
    free: Beam | None

    @property
    def snr(self):
        return self.peak / self.rms


def fit_core(m, search_radius=None, near=(0.0, 0.0)):
    """Fit the core of map `m`.

    The core is taken to be the brightest pixel within `search_radius` mas
    (default: twice the beam major axis) of `near` (mas from the reference
    pixel). A Gaussian with the restoring-beam shape, free in peak and
    position, is fitted to the pixels inside the beam's half-power contour
    around it. The position errors are the formal ones, scaled by the noise
    and by the number of pixels per beam since neighbouring pixels are
    correlated.
    """
    if search_radius is None:
        search_radius = 2 * m.beam.bmaj
    x, y = m.axes()
    xx, yy = np.meshgrid(x, y)
    inside = ((xx - near[0]) ** 2 + (yy - near[1]) ** 2 <= search_radius ** 2) & np.isfinite(m.data)
    if not inside.any():
        raise PrepError("%s: no pixel within %g mas of (%g, %g) mas."
                        % (m.name(), search_radius, near[0], near[1]))
    j, i = np.unravel_index(np.argmax(np.where(inside, m.data, -np.inf)), m.data.shape)
    x_peak, y_peak, peak = xx[j, i], yy[j, i], m.data[j, i]
    if peak <= 0:
        raise PrepError("%s: no positive peak within %g mas of (%g, %g) mas."
                        % (m.name(), search_radius, near[0], near[1]))
    pixel = np.abs(m.scales).mean()
    rms = noise_rms(m.data)
    cov_inv = np.linalg.inv(m.beam.cov())
    beam = _gauss(xx, yy, x_peak, y_peak, cov_inv)

    sel = (beam >= 0.5) & np.isfinite(m.data)
    xs, ys, zs = xx[sel], yy[sel], m.data[sel]
    fit = optimize.least_squares(lambda p: p[0] * _gauss(xs, ys, p[1], p[2], cov_inv) - zs,
                                 [peak, x_peak, y_peak], x_scale=[peak, pixel, pixel])
    a, x0, y0 = fit.x
    beam_pixels = m.beam.area() / np.abs(np.prod(m.scales))
    try:
        cov = np.linalg.inv(fit.jac.T @ fit.jac) * rms ** 2 * beam_pixels
        x_err, y_err = np.sqrt(np.diag(cov))[1:]
    except np.linalg.LinAlgError:
        x_err = y_err = np.nan

    # Free shape, over the beam's 25% contour so that the size is constrained.
    sel = (beam >= 0.25) & np.isfinite(m.data)
    xs, ys, zs = xx[sel], yy[sel], m.data[sel]

    def residual(p):
        inv = np.linalg.inv(_cov(abs(p[3]) + 1e-9, abs(p[4]) + 1e-9, p[5]))
        return p[0] * _gauss(xs, ys, p[1], p[2], inv) - zs

    try:
        free = optimize.least_squares(residual, [a, x0, y0, m.beam.bmaj, m.beam.bmin, m.beam.bpa],
                                      x_scale=[abs(a) or peak, pixel, pixel, m.beam.bmin, m.beam.bmin, 10])
        free = Beam.from_cov(_cov(abs(free.x[3]), abs(free.x[4]), free.x[5]))
    except (ValueError, np.linalg.LinAlgError):
        free = None
    return CoreFit(float(x0), float(y0), float(x_err), float(y_err), float(a), float(rms), free)


@dataclasses.dataclass(frozen=True)
class Grid:
    """Square grid of n x n pixels of `pixel` mas. The reference pixel is
    index n // 2 along both axes, and x increases to the east (to the left)."""

    n: int
    pixel: float

    @property
    def ref(self):
        return self.n // 2

    def axes(self):
        k = np.arange(self.n) - self.ref
        return -k * self.pixel, k * self.pixel

    def __str__(self):
        return "%d x %d px at %g mas" % (self.n, self.n, self.pixel)


def default_grid(maps, pixel=None, n=None):
    """The grid with the finest input pixel (or `pixel`) over the smallest
    input field (or n pixels), so that no map leaves part of it empty."""
    if pixel is None:
        pixel = min(np.abs(m.scales).min() for m in maps)
    if n is None:
        field = min(min(m.data.shape[1] * abs(m.scales[0]), m.data.shape[0] * abs(m.scales[1]))
                    for m in maps)
        n = int(round(field / pixel))
        n += n % 2
    if pixel <= 0 or n < 8:
        raise PrepError("Invalid output grid: %d px at %g mas." % (n, pixel))
    return Grid(n, float(pixel))


def restore(cc, x, y, beam):
    """Clean components `cc` (as in :class:`Map`) convolved with `beam` and
    evaluated on the grid with axes `x` and `y` (mas, evenly spaced), in
    Jy/beam: a point component's peak equals its flux."""
    out = np.zeros((len(y), len(x)))
    if len(cc) == 0:
        return out
    # Point components at the same position add up.
    points = (cc[:, 3] == 0) & (cc[:, 4] == 0)
    keys, inverse = np.unique(np.round(cc[points, 1:3], 9), axis=0, return_inverse=True)
    merged = np.zeros((len(keys), 6))
    merged[:, 0] = np.bincount(inverse.ravel(), weights=cc[points, 0])
    merged[:, 1:3] = keys
    components = np.concatenate([merged, cc[~points]])

    dx, dy = x[1] - x[0], y[1] - y[0]
    beam_cov = beam.cov()
    for flux, x0, y0, bmaj, bmin, bpa in components:
        if flux == 0:
            continue
        cov = beam_cov + _cov(bmaj, bmin, bpa)
        peak = flux * beam.bmaj * beam.bmin / np.sqrt(np.linalg.det(cov))
        # Pixels within N_SIGMA standard deviations along each axis.
        wx, wy = N_SIGMA * np.sqrt(np.diag(cov) / (2 * FOUR_LN2))
        i1, i2 = sorted(((x0 - wx - x[0]) / dx, (x0 + wx - x[0]) / dx))
        j1, j2 = sorted(((y0 - wy - y[0]) / dy, (y0 + wy - y[0]) / dy))
        i1, i2 = max(int(np.floor(i1)), 0), min(int(np.ceil(i2)), len(x) - 1)
        j1, j2 = max(int(np.floor(j1)), 0), min(int(np.ceil(j2)), len(y) - 1)
        if i1 > i2 or j1 > j2:
            continue
        xx, yy = np.meshgrid(x[i1:i2 + 1], y[j1:j2 + 1])
        out[j1:j2 + 1, i1:i2 + 1] += peak * _gauss(xx, yy, x0, y0, np.linalg.inv(cov))
    return out


def resample(data, ix, iy):
    """Sample `data` at the pixel coordinates ix (columns) x iy (rows), both
    evenly spaced, with a cubic spline. Points outside `data` are zero, and so
    are NaN pixels."""
    return ndimage.affine_transform(np.nan_to_num(data), [iy[1] - iy[0], ix[1] - ix[0]],
                                    offset=[iy[0], ix[0]], output_shape=(len(iy), len(ix)),
                                    order=3, mode="grid-constant", cval=0.0)


def convolve(data, dcov, pixel):
    """Convolve `data`, on a grid of `pixel` mas with x increasing to the left,
    with a unit-sum Gaussian of FWHM^2 covariance `dcov` (mas^2). The kernel
    may be degenerate, as when it widens a beam in one direction only."""
    c = dcov / pixel ** 2 / (2 * FOUR_LN2)
    # Pixel x runs west, so the x-y covariance changes sign.
    cxx, cyy, cxy = c[0, 0], c[1, 1], -c[0, 1]
    pad = int(np.ceil(N_SIGMA * np.sqrt(max(cxx, cyy, 0)))) + 1
    padded = np.pad(data, pad)
    ky = np.fft.fftfreq(padded.shape[0])[:, None]
    kx = np.fft.rfftfreq(padded.shape[1])[None, :]
    transfer = np.exp(-2 * np.pi ** 2 * (cxx * kx ** 2 + 2 * cxy * kx * ky + cyy * ky ** 2))
    out = np.fft.irfft2(np.fft.rfft2(padded) * transfer, s=padded.shape)
    return out[pad:pad + data.shape[0], pad:pad + data.shape[1]]


def _check_beam(m, beam):
    # Without clean components, a map can only be convolved to a wider beam.
    if m.cc is None and beam != m.beam and not beam.contains(m.beam):
        raise PrepError("%s has no clean components, so it can only be convolved to a beam that "
                        "contains its own (%s); %s doesn't." % (m.name(), m.beam, beam))


def prepare_map(m, grid, offset, beam=None):
    """Return map `m` resampled onto `grid`, with the sky position `offset`
    (mas from m's reference pixel) on the grid's reference pixel, and with
    `beam` (default: the map's own). Also return how it was made.

    With clean components, the model is restored exactly on the new grid and
    only the residual map is interpolated (the residual keeps its original
    resolution). Without them the map is interpolated, then convolved to
    `beam` if that differs from the map's beam, which it has to contain.
    """
    if beam is None:
        beam = m.beam
    x_out, y_out = grid.axes()
    ix = m.pix_ref[0] + (x_out + offset[0]) / m.scales[0]
    iy = m.pix_ref[1] + (y_out + offset[1]) / m.scales[1]
    if m.cc is not None:
        x_in, y_in = m.axes()
        residual = m.data - restore(m.cc, x_in, y_in, m.beam)
        cc = m.cc.copy()
        cc[:, 1] -= offset[0]
        cc[:, 2] -= offset[1]
        return resample(residual, ix, iy) + restore(cc, x_out, y_out, beam), "clean components"
    data = resample(m.data, ix, iy)
    if beam == m.beam:
        return data, "interpolated"
    _check_beam(m, beam)
    data = convolve(data, beam.cov() - m.beam.cov(), grid.pixel) * beam.area() / m.beam.area()
    return data, "interpolated, convolved"


def _sky_offset(m, ref):
    # Offset (mas) of the sky position `ref` (RA, Dec in deg) from m's reference pixel.
    dec = np.radians(m.crval[1])
    return np.array([(ref[0] - m.crval[0]) * np.cos(dec), ref[1] - m.crval[1]]) * MAS_PER_DEG


def write_map(path, data, m, grid, offset, beam, history, centered=False):
    """Write `data` (on `grid`) as a FITS map whose reference pixel is at the
    sky position `offset` mas from m's reference pixel. Keeps m's
    frequency and Stokes axes, observation keywords and epoch. `centered`
    (the offset is m's core) is recorded as PREP_CEN, and wise doesn't align
    such maps on a core offset file."""
    header_in = m.image.header
    extra = [k for k in range(3, header_in.get("NAXIS", 2) + 1) if header_in.get("NAXIS%d" % k) == 1]
    hdu = fits.PrimaryHDU(data.astype(np.float32).reshape((1,) * len(extra) + data.shape))
    h = hdu.header
    dec = np.radians(m.crval[1])
    ctypes = list(m.image.wcs.wcs.ctype)
    h["CTYPE1"] = ctypes[0]
    h["CRVAL1"] = m.crval[0] + offset[0] / MAS_PER_DEG / np.cos(dec)
    h["CDELT1"] = -grid.pixel / MAS_PER_DEG
    h["CRPIX1"] = grid.ref + 1
    h["CUNIT1"] = "deg"
    h["CTYPE2"] = ctypes[1]
    h["CRVAL2"] = m.crval[1] + offset[1] / MAS_PER_DEG
    h["CDELT2"] = grid.pixel / MAS_PER_DEG
    h["CRPIX2"] = grid.ref + 1
    h["CUNIT2"] = "deg"
    for axis, k in enumerate(extra, start=3):
        for key in ("CTYPE", "CRVAL", "CDELT", "CRPIX", "CUNIT"):
            if "%s%d" % (key, k) in header_in:
                h["%s%d" % (key, axis)] = header_in["%s%d" % (key, k)]
    h["BMAJ"] = beam.bmaj / MAS_PER_DEG
    h["BMIN"] = beam.bmin / MAS_PER_DEG
    h["BPA"] = beam.bpa
    if m.epoch is not None:
        midnight = m.epoch == datetime.datetime(m.epoch.year, m.epoch.month, m.epoch.day)
        h["DATE-OBS"] = m.epoch.strftime("%Y-%m-%d" if midnight else "%Y-%m-%dT%H:%M:%S")
    for key in ("OBJECT", "TELESCOP", "INSTRUME", "OBSERVER", "BUNIT", "EQUINOX", "RADESYS",
                "OBSRA", "OBSDEC"):
        if key in header_in:
            h[key] = header_in[key]
    h["ORIGFILE"] = (m.name(), "Map this one was prepared from")
    h["PREP_DX"] = (float(offset[0]), "[mas] RA offset of CRPIX in ORIGFILE")
    h["PREP_DY"] = (float(offset[1]), "[mas] Dec offset of CRPIX in ORIGFILE")
    h["PREP_CEN"] = (bool(centered), "Core on CRPIX: no core offset alignment")
    for line in history:
        h["HISTORY"] = line
    hdu.writeto(path, overwrite=True)


def _check_duplicate_days(maps):
    days = {}
    for m in maps:
        if m.epoch is None:
            continue
        day = m.epoch.strftime("%Y-%m-%d")
        if day in days:
            logger.warning("%s and %s are both from %s; a core offset file holds one position "
                           "per day, so the later one is used.", days[day], m.name(), day)
        days[day] = m.name()


def measure_cores(ctx, search_radius=None, near=(0.0, 0.0)):
    """Fit the core of each of ctx's files. Return a list of (Map, CoreFit)."""
    results = []
    for path in ctx.files:
        m = Map(ctx, path)
        fit = fit_core(m, search_radius=search_radius, near=near)
        logger.info("%s: core at (%+.4f, %+.4f) mas", m.name(), fit.x, fit.y)
        results.append((m, fit))
    _check_duplicate_days([m for m, _ in results])
    return results


def write_core_file(results, filename, unit=u.mas):
    """Write the core positions of `results` (as from :func:`measure_cores`)
    to a core offset file, with offsets in `unit`."""
    cores = wiseutils.CoreOffsetPositions()
    k = u.mas.to(unit)
    for m, fit in results:
        cores.set(m.epoch, [fit.x * k, fit.y * k])
    cores.save(filename, header="Core offsets from wise core %s, %s. Columns: epoch, id (unused), "
                                "r (%s), PA (deg east of north), from the reference pixel."
                                % (wise.__version__, datetime.date.today().isoformat(), unit))


def core_table(results):
    """Format `results` (as from :func:`measure_cores`) as a table."""
    header = ["Epoch", "File", "Core x, y (mas)", "Error x, y (mas)", "SNR",
              "Beam (mas, deg)", "Free fit (mas, deg)"]
    rows = []
    for m, fit in results:
        free = "%.3f x %.3f, %.1f" % (fit.free.bmaj, fit.free.bmin, fit.free.bpa) if fit.free else "-"
        rows.append([m.image.get_epoch(str_format="%Y-%m-%d"), m.name(),
                     "%+.4f, %+.4f" % (fit.x, fit.y), "%.4f, %.4f" % (fit.x_err, fit.y_err),
                     "%.0f" % fit.snr, "%.3f x %.3f, %.1f" % (m.beam.bmaj, m.beam.bmin, m.beam.bpa), free])
    return nputils.format_table(rows, header)


def prepare_files(ctx, outdir, beam="native", pixel=None, size=None, center=True,
                  search_radius=None, near=(0.0, 0.0), overwrite=False):
    """Prepare ctx's files into `outdir`: put them on one grid (by default
    :func:`default_grid`) with the core (or, without `center`, the first map's
    reference position) on the reference pixel. `beam` is "native" (keep each
    map's beam), "common" (:func:`common_beam`) or a :class:`Beam`.

    Writes one map per input, with the same file name, and a log. Return
    the grid, the beam used for all maps (None for "native") and the table
    of what was done.
    """
    maps = [Map(ctx, path) for path in ctx.files]
    outputs = [os.path.join(outdir, m.name()) for m in maps]
    if len(set(outputs)) < len(outputs):
        raise PrepError("Two input files have the same name; they would be written to the same "
                        "output file.")
    log_path = os.path.join(outdir, LOG_FILENAME)
    for m, out in zip(maps, outputs):
        if os.path.abspath(out) == os.path.abspath(m.path):
            raise PrepError("%s would overwrite its input; choose another output directory." % out)
    existing = [p for p in outputs + [log_path] if os.path.exists(p)]
    if existing and not overwrite:
        raise PrepError("%s already exists; use --overwrite to replace it." % existing[0])

    grid = default_grid(maps, pixel=pixel, n=size)
    if beam == "native":
        target = None
    elif beam == "common":
        target = common_beam([m.beam for m in maps])
        logger.info("Common beam: %s", target)
    else:
        target = beam
    if target is not None:
        for m in maps:
            _check_beam(m, target)
    _check_duplicate_days(maps)

    if center:
        fits_ = [fit_core(m, search_radius=search_radius, near=near) for m in maps]
        offsets = [(f.x, f.y) for f in fits_]
    else:
        # Keep the sky position of the first map's reference pixel.
        fits_ = [None] * len(maps)
        offsets = [_sky_offset(m, maps[0].crval) for m in maps]

    os.makedirs(outdir, exist_ok=True)
    version = "wise prep %s" % wise.__version__
    rows = []
    for m, out, offset, fit in zip(maps, outputs, offsets, fits_):
        b = target or m.beam
        if target is not None and m.cc is not None and not target.contains(m.beam):
            logger.warning("%s: %s is narrower than the map's own beam (%s) in some direction; "
                           "the residual map keeps its original resolution.", m.name(), target, m.beam)
        data, method = prepare_map(m, grid, offset, b)
        if center:
            where = "core at (%+.4f, %+.4f) mas from the reference pixel of %s moved to CRPIX" % (
                offset[0], offset[1], m.name())
        else:
            where = "reference position of the first map kept on CRPIX"
        history = ["%s: regridded to %s; %s." % (version, grid, where),
                   "%s: %s; beam %s." % (version, method, b)]
        write_map(out, data, m, grid, offset, b, history, centered=center)
        rows.append([m.image.get_epoch(str_format="%Y-%m-%d"), m.name(),
                     "%+.4f, %+.4f" % tuple(offset) if center else "-",
                     "%.4f, %.4f" % (fit.x_err, fit.y_err) if fit else "-",
                     "%.0f" % fit.snr if fit else "-",
                     "%.3f x %.3f, %.1f" % (b.bmaj, b.bmin, b.bpa), method])
        logger.info("%s -> %s (%s)", m.path, out, method)

    header = ["Epoch", "File", "Core x, y (mas)" if center else "Core x, y", "Error x, y (mas)", "SNR",
              "Beam (mas, deg)", "Method"]
    table = nputils.format_table(rows, header)
    with open(log_path, "w") as f:
        f.write("# %s, %s\n" % (version, datetime.date.today().isoformat()))
        f.write("# Grid: %s; reference pixel (FITS) %d, %d.\n" % (grid, grid.ref + 1, grid.ref + 1))
        f.write("# Beam: %s.\n" % ("native" if target is None else target))
        if center:
            f.write("# Each map's core is on the reference pixel (PREP_CEN = T), so wise doesn't "
                    "align these maps on a core offset file.\n")
        f.write(table + "\n")
    return grid, target, table
