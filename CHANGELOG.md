# Changelog

All notable changes to wise-wavelets are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.5.0.dev0] — 2026-05-07

First release of the modernization fork. Both packages (`libwise`, `wisetool`)
now target Python 3.11+ and a current scientific-Python stack. See
`MIGRATION_NOTES.md` for the per-substitution log.

### Changed

- **Python 2 → 3.11+.** Ran `2to3` against upstream, then hand-fixed implicit
  relative imports, removed-stdlib usage (`ConfigParser`, `cStringIO`,
  `imghdr`, `types.NoneType`), and Py3 true-division leftovers that `2to3`
  doesn't catch.
- **Repo restructure.** Monorepo with two packages under `packages/libwise/`
  and `packages/wise/`, both using the `src/` layout and `hatchling` build
  backend. Conda `environment.yml` at the root is the source of truth for dev
  dependencies.
- **Dependencies replaced.**
  - `pymorph` → `scikit-image` (one call site, `pymorph.secross` →
    `skimage.morphology.diamond`).
  - `scipy.ndimage.{filters,interpolation,measurements,morphology}` →
    `scipy.ndimage` direct.
  - `scipy.misc` → `imageio.v3` / `skimage.transform.resize` /
    `skimage.data` (per call site).
  - `pkg_resources` → `importlib.resources` (setuptools 81 dropped
    `pkg_resources` from the default install).
  - `matplotlib.mlab.dist_point_to_segment` → inlined six-line
    implementation.
  - `mpl_toolkits.axes_grid1.anchored_artists.AnchoredEllipse` →
    inlined upstream class (removed in matplotlib 3.8).
- **numpy 2.x.** Replaced bare `np.int` / `np.float` / `np.complex` aliases
  with their Python builtins; wrapped list-of-slices indexing in `tuple(...)`
  per the numpy 2.0 strictness change.
- **scikit-image 0.19+.** `skimage.morphology.watershed` →
  `skimage.segmentation.watershed`.
- **Qt UI.** PyQt4 fallback dropped; standardized on **PyQt5** with explicit
  `QtCore` / `QtGui` / `QtWidgets` qualification (no `setattr` shim). Backend
  switched to `matplotlib.backends.backend_qt5agg`. `QFileDialog.get*Name`
  call sites updated for the PyQt5 tuple return.
- **CLI.** New `wise.cli:main` entry point replaces the legacy
  `scripts/wise` shebang script.

### Verified

- `pytest packages/libwise/tests packages/wise/tests` — 51 passed, 8 skipped.
  The skips are upstream tests that targeted functions that were never
  implemented or were left as `assert False` debug stubs; each is documented
  in `MIGRATION_NOTES.md`.
- `wise --help` lists all 12 actions discovered from `wise.actions`.
- `python -c "import libwise, wise; print(libwise.get_version(), wise.get_version())"`
  succeeds.
- All Qt UI modules (`libwise.app.PolyRegionEditor`, `WaveletBrowser`,
  `WaveletDenoise`, `Wavelet2DBrowser`, …) import cleanly under PyQt5 5.15.

### Deferred

- End-to-end Qt widget instantiation against real datasets — modules import,
  but interactive launch is not yet smoke-tested here.
- Optional cleanups: replacing the vendored `appdirs` import path with
  `platformdirs`, replacing custom `jsonpickle_numpy.py` with
  `jsonpickle.ext.numpy`, refactoring `pyregion` usage onto the modern
  `regions` library.
