"""The offset view of the separation-from-core plot (``wise plot sep --offset``).

Each link is drawn as its change in distance from core since its first epoch,
on its own baseline, so that slow motion is visible. Baselines are stacked by
mean distance from core and spaced so that no two tracks overlap.
"""
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pytest
from click.testing import CliRunner

fits = pytest.importorskip("astropy.io.fits")

import wise
from libwise import imgutils, nputils
from wise import tasks, wiseutils
from wise.cli import cli


# ---------------------------------------------------------------------------
# offset_baselines
# ---------------------------------------------------------------------------

def test_baselines_are_stacked_by_mean_distance_innermost_first():
    dfcs = [[18.0, 18.1], [0.1, 0.1], [3.4, 3.9]]
    baselines, step = wiseutils.offset_baselines(dfcs)
    assert baselines[1] == 0
    assert baselines[2] == step
    assert baselines[0] == 2 * step


def test_automatic_step_keeps_tracks_apart():
    rng = np.random.default_rng(1)
    # Tracks moving out, moving in and wandering, at various distances.
    dfcs = [r0 + np.cumsum(rng.normal(v, 0.3, 6))
            for r0, v in [(0.1, 0.0), (3.0, 0.5), (7.0, -0.4), (15.0, 0.1), (25.0, 1.0)]]
    baselines, step = wiseutils.offset_baselines(dfcs)
    tracks = sorted((b + np.asarray(d) - d[0] for b, d in zip(baselines, dfcs)),
                    key=lambda t: t[0])
    for lower, upper in zip(tracks, tracks[1:]):
        assert lower.max() < upper.min()


def test_explicit_step_is_used():
    baselines, step = wiseutils.offset_baselines([[1.0, 2.0], [5.0, 9.0]], step=0.5)
    assert step == 0.5
    assert list(baselines) == [0, 0.5]


def test_tracks_that_do_not_move_get_a_unit_step():
    baselines, step = wiseutils.offset_baselines([[1.0, 1.0], [5.0, 5.0]])
    assert step == 1.0
    assert list(baselines) == [0, 1.0]


# ---------------------------------------------------------------------------
# On a real match result
# ---------------------------------------------------------------------------

def _gaussian_2d(shape, center, sigma=2.5, amplitude=1.0):
    yy, xx = np.indices(shape)
    cy, cx = center
    return amplitude * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * sigma**2))


def _write_fits(path, data, date_obs):
    hdu = fits.PrimaryHDU(data.astype(np.float32))
    h = hdu.header
    h["DATE-OBS"] = date_obs
    h["BMAJ"], h["BMIN"], h["BPA"] = 1e-4, 1e-4, 0.0
    h["CTYPE1"], h["CRVAL1"], h["CDELT1"], h["CRPIX1"] = "RA---SIN", 0.0, -1e-5, data.shape[1] / 2
    h["CTYPE2"], h["CRVAL2"], h["CDELT2"], h["CRPIX2"] = "DEC--SIN", 0.0, 1e-5, data.shape[0] / 2
    hdu.writeto(str(path), overwrite=True)
    return str(path)


@pytest.fixture
def matched_ctx(tmp_path, monkeypatch):
    """Three epochs of a bright core and a knot moving slowly outward."""
    (tmp_path / ".wise").mkdir()
    monkeypatch.chdir(tmp_path)

    shape = (64, 64)
    rng = np.random.default_rng(42)
    paths = []
    for i, date in enumerate(["2026-01-01", "2026-02-01", "2026-03-01"]):
        data = (_gaussian_2d(shape, (32, 24), sigma=3.0, amplitude=1.0)
                + _gaussian_2d(shape, (32, 42 + i), sigma=2.5, amplitude=0.6)
                + rng.normal(0, 0.001, shape))
        paths.append(_write_fits(tmp_path / f"epoch_{i:02d}.fits", data, date))

    ctx = wise.AnalysisContext()
    ctx.config.finder.min_scale = 2
    ctx.config.finder.max_scale = 3
    ctx.config.finder.alpha_threshold = 10
    ctx.config.finder.alpha_detection = 15
    ctx.config.data.bg_use_ksigma_method = True
    ctx.select_files(paths)
    tasks.match_all(ctx)
    return ctx


def _links_and_projection(ctx):
    projection = ctx.get_projection(ctx.get_ref_image())
    scale = ctx.result.get_scales()[0]
    _, link_builders = ctx.get_match_result()
    links = list(link_builders.get_scale(scale).get_links(min_link_size=2))
    assert len(links) >= 2, "the synthetic data should give at least two links"
    return links, projection


def test_each_link_starts_on_its_own_baseline(matched_ctx):
    links, projection = _links_and_projection(matched_ctx)
    fig, ax = plt.subplots()
    y_shift = wiseutils.plot_links_dfc_baselines(ax, projection, links)
    starts = [projection.dfc(imgutils.p2i(link.first().get_coord('com'))) + y_shift[link]
              for link in links]
    baselines = sorted(line.get_ydata()[0] for line in ax.get_lines())
    assert sorted(starts) == pytest.approx(baselines)
    assert len(set(np.round(baselines, 9))) == len(links)
    plt.close(fig)


def test_offset_leaves_the_fits_unchanged(matched_ctx):
    # get_links keeps links longer than min_link_size: these have 3+ epochs.
    kwargs = dict(fit_fct=nputils.LinearFct, min_link_size=2)
    plain = tasks.plot_separation_from_core(matched_ctx, save_filename="plain.png", **kwargs)
    offset = tasks.plot_separation_from_core(matched_ctx, save_filename="offset.png",
                                             offset=True, **kwargs)
    assert plain
    assert {l.get_id(): f.a for l, f in offset.items()} == \
        pytest.approx({l.get_id(): f.a for l, f in plain.items()})


def test_cli_offset_step_must_be_positive():
    result = CliRunner().invoke(cli, ["plot", "sep", "run1", "4", "--offset-step", "0"])
    assert result.exit_code == 2
    assert "--offset-step" in result.output


def test_cli_plot_sep_help_lists_offset_options():
    result = CliRunner().invoke(cli, ["plot", "sep", "--help"])
    assert result.exit_code == 0, result.output
    assert "--offset" in result.output
    assert "--offset-step" in result.output
