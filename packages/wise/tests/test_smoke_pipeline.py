"""Integration smoke test for the detect → match pipeline.

Locks in the regressions caught by the first-user 3C120 walkthrough
(MIGRATION_NOTES.md Phase 8). The point is *not* scientific correctness;
the assertions only check that the orchestration layer completes without
traceback against a tiny synthetic dataset.
"""
import numpy as np
import pytest

pytest.importorskip("astropy")
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
def synthetic_fits_pair(tmp_path):
    shape = (64, 64)
    rng = np.random.default_rng(42)
    # Very low noise floor — combinatorial explosion in the matcher's
    # optimize() step is triggered when too many noise-driven features
    # cross the wavelet detection threshold.
    noise_sigma = 0.001

    # Two epochs with two gaussians each; the second epoch has a small
    # positional shift to give the matcher something non-trivial to do.
    epoch1 = (
        _gaussian_2d(shape, (32, 24), sigma=3.0, amplitude=1.0)
        + _gaussian_2d(shape, (32, 42), sigma=2.5, amplitude=0.6)
        + rng.normal(0, noise_sigma, shape)
    )
    epoch2 = (
        _gaussian_2d(shape, (32, 25), sigma=3.0, amplitude=1.0)
        + _gaussian_2d(shape, (33, 43), sigma=2.5, amplitude=0.6)
        + rng.normal(0, noise_sigma, shape)
    )

    paths = []
    try:
        for i, (data, date) in enumerate(
            [(epoch1, "2026-01-01"), (epoch2, "2026-02-01")]
        ):
            p = tmp_path / f"smoke_{i:02d}.fits"
            _write_fits(str(p), data, date)
            paths.append(str(p))
    except Exception as e:
        pytest.skip(f"FITS write failed in test environment: {e}")

    return paths


def test_detect_then_match_completes(synthetic_fits_pair, tmp_path, monkeypatch):
    """detect → match runs end-to-end on a 2-epoch synthetic dataset
    without raising. Locks in the Phase 8 smoke-test fixes (cmp polyfill,
    Feature.__lt__, ImageRegion shift cast, configparser text mode,
    filter list-wrap, settings print formatting).
    """
    import wise

    # Mark tmp_path as a wise project root so context.get_data_dir() resolves
    # (called via ctx.detection → get_mask → _resolve_optional_file).
    (tmp_path / ".wise").mkdir(exist_ok=True)
    monkeypatch.chdir(tmp_path)

    ctx = wise.AnalysisContext()
    ctx.config.finder.min_scale = 2
    ctx.config.finder.max_scale = 3
    # Bump SNR thresholds well above the noise floor so only the
    # injected gaussians are detected — keeps the matcher's
    # combinatorial optimize() step bounded.
    ctx.config.finder.alpha_threshold = 10
    ctx.config.finder.alpha_detection = 15
    ctx.config.data.bg_use_ksigma_method = True
    ctx.select_files(synthetic_fits_pair)

    assert len(ctx.files) == 2

    # detection_all + match-on-pair, mirroring tasks.match_all without
    # the print() side effect on an empty match_ratio_list.
    res1 = ctx.detection(ctx.open_file(ctx.files[0]), verbose=False)
    res2 = ctx.detection(ctx.open_file(ctx.files[1]), verbose=False)

    match_res = ctx.match(res1, res2, verbose=False)

    # We don't assert anything about match counts — synthetic gaussians
    # may or may not survive the matcher's intensity/correlation
    # thresholds. The point is just that no traceback is raised.
    assert match_res is not None
