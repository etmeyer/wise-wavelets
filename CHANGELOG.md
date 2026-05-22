# Changelog

All notable changes to wise-wavelets are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Click-based CLI** (F1, F2): `wise` is now a proper `click.Group`.
  All 12 subcommands (`info`, `stack`, `settings`, `detect`, `match`,
  `view`, `view_features`, `view_links`, `plot_features`,
  `plot_sep_from_core`, `region`, `select_files`) are registered as
  `@click.command` entries and inherit global flags:
  - `--verbose / -v` — INFO-level logging to stderr
  - `--quiet / -q` — ERROR-level only
  - `--debug` — DEBUG-level
  - `--non-interactive` — raises `UsageError` instead of prompting
  - `--version` — prints `wise <version> (libwise: <version>)`
  - `--help / -h` — standard click help on every command

- **Non-interactive scripting flags** for the previously prompt-only
  commands:
  - `wise detect --name NAME --save/--no-save --view-scales SCALES`
  - `wise match --name NAME --save/--no-save --view-scales SCALE`
  These allow fully unattended pipelines without `--non-interactive`.

- **Structured logging** (F2): status output (progress notes, warnings,
  internal debug lines) throughout `wise.project`, `wise.tasks`,
  `wise.wds`, `wise.matcher`, and `wise.wiseutils` now goes through
  `logging.getLogger(__name__)`. User-facing data output (`wise info`
  tables, `wise settings show` output) uses `click.echo()`.
  `logging.captureWarnings(True)` is wired at group startup, routing
  library warnings through the same handler (groundwork for the
  astropy `FITSFixedWarning` silencer in PR3/E5).

- **CliRunner smoke tests** (F7 baseline): `packages/wise/tests/
  test_cli_smoke.py` — 16 tests covering `--help` on every subcommand,
  `--version`, verbosity mutual-exclusion, and a non-interactive
  no-files clean-exit check.

### Changed

- `libwise.scriptshelper` is no longer imported by any
  `wise.actions.wise_*` module. The libwise standalone scripts
  (`wt-denoise`, `wt2d`, `fits-crop`) and `wise/contrib/` modules
  still use it; it is not deleted.
- `wise select_files --end-date` short option is `-e` (corrected from
  the old `-d` USAGE string, matching the original code behaviour).

## [0.5.0] — 2026-05-22

Promotes `0.5.0.dev1` to a stable release. Seven additional Py3
regressions were caught during real-data shakedown sessions (3C120 and a
faint VLBA X-band test source) and fixed before the final `0.5.0` cut.
This release establishes the reference point for the "compatible with
upstream wise behaviour" line; bug-fix-only backports will land on the
`0.5.x` maintenance branch. Active development on 1.0 (which includes
breaking UX and CLI changes catalogued in `_wise_improvement_plan.md`
and sequenced in `_wise_1_0_roadmap.md`) continues on `main`.

### Fixed

- `libwise.imgutils.fast_sorted_fits`: parse FITS 4.0 `DATE-OBS`
  variants including the ISO-with-time form (`2018-01-25T01:23:45.6`)
  used by VLBA correlator output. Previously crashed with
  `'<' not supported between instances of 'datetime.datetime' and
  'NoneType'` on the first such file because `guess_date` silently
  returned `None`. Warn-and-skip on any remaining unparseable header
  (timezone-suffixed forms, etc.) so one bad date no longer takes down
  the batch. The same widened format list is applied to
  `StackedImage.zero_header`. (#11, fixes #10.)
- `wise.project.AnalysisContext.get_core_offset` and `.get_mask`:
  short-circuit to `None` when `config.data.core_offset_filename` or
  `config.data.mask_filename` is unset, instead of crashing in
  `os.path.isfile(None)` with `TypeError: stat: path should be string,
  bytes, os.PathLike or integer, not NoneType`. Catalogued as
  improvement-plan item B4.
- `wise.wds`: widen watershed-marker dtype to `int32` to avoid
  signed-int overflow on dense detections. (#9)
- `libwise.imgutils`: support CASA-style multi-axis FITS by squeezing
  degenerate Stokes/frequency axes and using `WCS.celestial` for
  projection setup. (#8)
- `wise`: default `QT_API=pyqt5` at process start so matplotlib doesn't
  fall back to a tk backend and emit `ImportError: Failed to import any
  qt binding` when the Qt-backed plot windows open. (#6)
- `wise.project.AnalysisContext.get_ref_image`: split the previous
  catch-all `Exception` into `FileNotFoundError` (user-supplied
  reference-image path missing) and `RuntimeError` (no files selected
  before the call). Diagnostic messages now name the offending config
  key. (#5)

### Added

- `docs/data_formats.rst`: documents the `core.dat` plain-text format
  (PA convention east-of-north, units following
  `data.projection_unit`, epoch matching against `img.get_epoch()`).
  Previously implicit in the parser. (#7)
- `.gitignore` patterns: `testing/` for local scratch FITS fixtures not
  shipped with the repo, and `_[!_]*` for personal notes and planning
  files prefixed with a single underscore (the pattern intentionally
  excludes dunder names like `__init__.py`).

## [0.5.0.dev1] — 2026-05-07

First-user smoke test (3C120 walkthrough on 10 epochs of
`0430+052.u.2012_*.icn.fits`) caught seven Py2→Py3 regressions that
neither `2to3` nor the upstream pytest sweep exercised. Adding a
synthetic-FITS pytest to lock those in surfaced two more (FITS files
opened in text mode), giving nine total. All nine were mechanical
fixes; algorithm and I/O semantics unchanged. See `MIGRATION_NOTES.md`
Phase 8 for per-fix detail.

### Added

- `packages/wise/tests/test_smoke_pipeline.py`: integration smoke
  test driving `detection → match` against a synthetic 2-epoch 64×64
  FITS dataset. Locks in the Phase 8 regressions so future port
  drift in the orchestration layer fails pytest rather than waiting
  for a hand-run.

### Fixed

- `imgutils.fast_sorted_fits`: dropped `list(filter(date))` wrap where
  `filter` is a local-variable predicate, not the lazy builtin.
- `nputils.ConfigurationsContainer.to_file`: opened in text mode `'w'`
  (Py3 `configparser.RawConfigParser.write` requires `str`).
- `wise/actions/wise_settings.py`: dropped `list(...)` around
  `Configuration.values()` in `wise settings show`; `values()` returns a
  formatted string and `list(string)` iterated it into single characters.
- `cmp()` builtin polyfill: added `_cmp(a, b)` in `wise.features`,
  imported into `matcher`, `tasks`, `wds`, `wiseutils`. Rewrote
  `sorted(..., cmp=...)` sites via `functools.cmp_to_key` (or directly
  to `key=`). Added `Feature.__lt__` delegating to `__cmp__` so Py3
  `list.sort()` orders `Segment` instances.
- `imgutils.ImageRegion.set_shift`: cast `np.round(shift)` to `int` so
  downstream `slice(...)` indices are integers (Py3 strict).
- `imgutils.is_fits` and `imgutils.FastHeaderReader.read`: open FITS
  files in binary mode. Py3 text-mode default raised
  `UnicodeDecodeError` once the buffered decoder hit binary data
  past the (single-block) header; real .icn.fits headers happened
  to span multiple 2880-byte ASCII blocks and masked this.

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
