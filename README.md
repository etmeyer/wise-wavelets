# wise-wavelets

A Python 3 modernization of [WISE (Wavelet Image Segmentation and
Evaluation)](https://github.com/flomertens/wise) — a tool for
detecting and tracking features in multi-epoch radio interferometric
maps. Built for VLBI work on AGN jets, but applicable to any sequence
of co-registered sky maps where you want to find significant structure
and follow it across time.

The original WISE and its companion library `libwise` are Python 2
only and were last released in 2015. This fork ports both to a current
scientific-Python stack (Python 3.11+, numpy 2.x, scipy 1.16, astropy
≥6, scikit-image ≥0.22, matplotlib ≥3.9, PyQt5) and is under active
maintenance; see [Credit](#credit) below.

## What it does

Given a sequence of FITS images covering the same source at different
epochs, wise:

- runs a multi-scale wavelet decomposition on each image,
- segments the per-scale wavelet planes into features (peaks, blobs)
  above a user-specified significance threshold,
- matches features across epochs using position, scale, and an
  optional velocity prior,
- and produces kinematic plots — feature trajectories on the sky,
  separation-from-core vs. time, fit apparent velocities — either
  directly from the command line or as artifacts you can load into a
  notebook.

The MOJAVE 3C 120 walkthrough is the canonical worked example.

## Quick start

```bash
# Clone and install (conda; both packages installed editable)
git clone https://github.com/etmeyer/wise-wavelets
cd wise-wavelets
conda env create -f environment.yml
conda activate wise-wavelets

# Get a feel for the CLI
wise --help                     # list all 12 actions
wise info my_data_*.fits        # epoch / beam / pixel-scale summary
wise settings show              # full analysis config with defaults, units, ranges
wise detect --dry-run map.fits  # preview detection on one file before committing
```

A few quality-of-life notes for newcomers:

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
specific to this fork. The original
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

PyPI publication for `wisetool` and `libwise` from this fork is
planned alongside the 1.0 release.

## Which version to use

The default — cloning the repo as shown above — gives you the latest
stable release on `main`, currently **v0.6.0** (May 2026). It is
compatible with the original wise CLI and configuration schema, so
existing notebooks and config files from upstream continue to work.

If you're locked to an even-earlier snapshot and prefer not to track
the v0.6.0 improvements (added logging, unified settings table, loud
failure modes, etc.), there's a frozen maintenance line that matches
the upstream wise CLI exactly:

```bash
git clone --branch 0.5.x https://github.com/etmeyer/wise-wavelets
```

A future **1.0** release will introduce breaking renames (fixing the
upstream's misspelled `alpha_threashold` → `alpha_threshold`, removing
the `--nsigma_connected` flag in favor of `--keep_brightest_only`,
adding a `wise init` project-root concept). Those changes are in
progress; until 1.0 ships, `main` stays compatible with how upstream
wise behaves and how 0.5.x users expect it to behave.

## Credit

The original Python 2 codebase and the design of the
wavelet-segmentation + matching pipeline are due to Florent Mertens.
This fork tracks the same module structure and CLI surface.
`MIGRATION_NOTES.md` in the repo records the per-file substitutions
(pymorph → scikit-image, scipy submodule re-homing, numpy 2.x scalar
aliases, matplotlib backend rename, PyQt4 → PyQt5, and the per-test
triage).

## Issues, bugs, and maintenance

Please open an [issue](https://github.com/etmeyer/wise-wavelets/issues)
if you hit something broken or surprising — including documentation
gaps. Code in this fork is being written and reviewed with Claude
(Anthropic's Opus model) doing planning and Sonnet executing under a
plan; the migration log and the v0.6.0 work were carried out this
way. The intent is to keep this fork working as long as it's useful
for the community; feedback that nudges priorities is welcome.

## License

GPL-2.0, inherited from upstream.
