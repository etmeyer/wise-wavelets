# wise-wavelets

A maintained Python 3 version of
[WISE (Wavelet Image Segmentation and Evaluation)](https://github.com/flomertens/wise),
the method and software by **Florent Mertens** for detecting and
tracking features in multi-epoch radio interferometric maps
([Mertens & Lobanov 2015, A&A 574, A67](https://ui.adsabs.harvard.edu/abs/2015A%26A...574A..67M)).
WISE was built for VLBI work on AGN jets, but it works on any sequence
of sky maps of the same source where you want to find significant
structure and follow it across time.

The original WISE and its companion library `libwise` are Python 2
only and were last released in 2015. This fork ports both to a current
scientific-Python stack (Python 3.11+, numpy 2.x, scipy, astropy ≥6,
scikit-image, matplotlib, PyQt5) and is under active maintenance. The
current release is **v1.1.0** (October 2026); see the
[CHANGELOG](CHANGELOG.md).

<p align="center">
  <img src="https://raw.githubusercontent.com/etmeyer/wise-wavelets/main/docs/tutorials_notebook/imgs/3c120/view_links.png" width="49%" alt="3C 120 jet features tracked across epochs at the 0.4 mas wavelet scale">
  <img src="https://raw.githubusercontent.com/etmeyer/wise-wavelets/main/docs/tutorials_notebook/imgs/3c120/plot_separation_from_core_fit_scale4.png" width="49%" alt="Separation from the core versus time for the tracked 3C 120 features, with linear fits">
</p>
<p align="center"><sub>3C 120 at 15 GHz (MOJAVE, 2012–2013): features
tracked at the 0.4 mas wavelet scale (left) and their separation from
the core with linear fits (right). Figures from F. Mertens' original
WISE tutorial.</sub></p>

## What it does

Given a sequence of FITS images of the same source at different
epochs, wise:

- puts maps from different arrays or archives onto one pixel grid,
  centred on the core, optionally with a common restoring beam
  (`wise prep`), or measures core positions for sub-pixel alignment of
  maps that already share a grid (`wise core`),
- runs a multi-scale wavelet decomposition on each image,
- segments the per-scale wavelet planes into features (peaks, blobs)
  above a user-specified significance threshold,
- matches features across epochs using position, scale, and an
  optional velocity prior,
- and produces kinematic plots — feature trajectories on the sky,
  separation-from-core vs. time, fit apparent velocities — either
  directly from the command line or as results you can load into a
  notebook.

The MOJAVE 3C 120 walkthrough on the documentation site is the
canonical worked example.

## Quick start

```bash
# Clone and install (conda; both packages installed editable)
git clone https://github.com/etmeyer/wise-wavelets
cd wise-wavelets
conda env create -f environment.yml
conda activate wise-wavelets

# Set up a project for one source, with your FITS maps in maps/
cd /path/to/my_source
wise init                                      # marks this directory as a wise project
wise show info maps/*.fits                     # epoch / beam / pixel-scale summary
wise prep maps/*.fits -o prep                  # only needed if the maps' grids differ
wise settings show                             # every setting, with defaults, units, ranges
wise settings set data.bg_coords=10,10,30,30   # a source-free box (mas) for the noise
wise detect --dry-run prep/one_map.fits        # preview detection on one map
wise match prep/*.fits --save --name run1      # detect, match, and save as run1
wise plot sep run1 4,8 --fit                   # separation from core vs. time, with fits
```

`wise --help` lists every command, and `wise COMMAND --help` its
options. A few notes for newcomers:

- wise refuses inputs it can't combine correctly — maps on different
  pixel grids (use `wise prep`) or two maps from the same day — and
  says which files are the problem.
- `wise -v <cmd>` adds informational logging (e.g. resolved background
  region, alignment epochs). `--debug` adds everything.
- `wise settings show` flags configuration issues (e.g. no background
  extraction method set) at the bottom of the table.
- `wise detect --dry-run` previews per-scale peak counts at the
  configured significance threshold *and* at a lower α=1.5 bound,
  which makes empirical tuning easy on faint or diffuse sources where
  the default α=4 finds nothing.

## Documentation

Rendered documentation site: <https://etmeyer.github.io/wise-wavelets/>

The site mirrors the upstream wise documentation and adds notes
specific to this fork, including the [file formats](https://etmeyer.github.io/wise-wavelets/data_formats.html)
wise reads and writes. The original
[flomertens/wise tutorial](https://flomertens.github.io/wise/) is also
available; its data links are dead, but the 2012 3C 120 Stokes-I
images it uses can still be downloaded from the
[MOJAVE source page for 0430+052](https://www.cv.nrao.edu/MOJAVE/sourcepages/0430+052.shtml).

## Installation

Conda is the recommended path — several of the dependencies install
more reliably from conda-forge than from PyPI:

```bash
git clone https://github.com/etmeyer/wise-wavelets
cd wise-wavelets
conda env create -f environment.yml
conda activate wise-wavelets
```

A pure-pip install also works:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e packages/libwise
pip install -e packages/wise
pip install PyQt5   # needed for the GUI viewers
```

This version is not on PyPI. The `wisetool` and `libwise` packages
there (and on the `flomertens` conda channel) are the original
Python 2 release, 0.4.7, so `pip install wisetool` will not give you
this code.

## Which version to use

Use the latest release on `main` (cloning as shown above gives you
this). If you are coming from upstream wise or from this fork's 0.5 or
0.6 releases, note that 1.0 changed the project layout and renamed a
few settings and flags (for example the misspelled `alpha_threashold`
is now `alpha_threshold`). `wise upgrade-config` converts an existing
project in place:

```bash
cd my_old_project
wise upgrade-config --dry-run .   # preview the changes
wise upgrade-config .
```

If you need to reproduce older results exactly, the frozen `0.5.x`
branch matches the upstream wise CLI and configuration:

```bash
git clone --branch 0.5.x https://github.com/etmeyer/wise-wavelets
```

## Credit

The method, the original Python 2 codebase, and the design of the
wavelet-segmentation and matching pipeline are due to Florent Mertens.
If you use WISE in published work, please cite:

- Mertens, F. & Lobanov, A. P. 2015, A&A, 574, A67 —
  [*Wavelet-based decomposition and analysis of structural patterns in
  astronomical images*](https://ui.adsabs.harvard.edu/abs/2015A%26A...574A..67M)
- Mertens, F. & Lobanov, A. P. 2016, A&A, 587, A52 —
  [*Detection of multiple velocity components in partially overlapping
  emitting regions*](https://ui.adsabs.harvard.edu/abs/2016A%26A...587A..52M)
  (stacked cross-correlation)

This fork keeps the original module structure. `MIGRATION_NOTES.md`
in the repo records the per-file substitutions made in the Python 3
port (pymorph → scikit-image, scipy submodule re-homing, numpy 2.x
scalar aliases, matplotlib backend rename, PyQt4 → PyQt5, and the
per-test triage).

## Issues, bugs, and maintenance

Please open an [issue](https://github.com/etmeyer/wise-wavelets/issues)
if you hit something broken or surprising — including documentation
gaps. Code in this fork is written and reviewed with Claude
(Anthropic), under plans the maintainer reviews; every change goes
through a pull request and the test suite. The intent is to keep this
fork working as long as it's useful for the community; feedback that
nudges priorities is welcome.

## License

GPL-2.0, inherited from upstream.
