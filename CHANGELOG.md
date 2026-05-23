# Changelog

All notable changes to wise-wavelets are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Phase 2 of the wise 1.0 plan ("the clean break"), in progress. PR5
introduced the project-root concept; PR7 builds on it with the
`wise plot` / `wise show` subcommand regrouping and the `.wiseproj/`
result bundle layout. The remaining clean-break PRs (PR6 result-name
matching + key renames, PR8 `wise upgrade-config`) depend on what
landed here.

### Added

- **`wise init [DIRECTORY]`** (F3.2): seeds a new wise project. Creates
  `DIRECTORY/.wise/` (the project-root marker, also used for caches and
  result bundles), writes a default `DIRECTORY/wise_config` if none
  exists, and appends `.wise/` to `DIRECTORY/.gitignore` (creating one
  if missing). Refuses to re-initialize an existing project. Default
  `DIRECTORY` is the current directory.

- **`wise.find_project_root([start])`** (F3.1): resolver that walks
  upward from `start` (default cwd) looking for `.wise/`, returning the
  absolute path to the containing directory, or `None`. Same semantics
  as `git`'s repo-root resolver — `wise` commands now work from
  anywhere inside a project tree.

- **`wise project`** (F4.3): prints the resolved project root and exits,
  raising the standard `ProjectRootNotFound` UsageError outside a
  project. Replaces PR5's interim `wise info --project` flag.

- **"Project root: \<abs-path\>" header** (F3.5) in `wise settings
  show` output, above the section tables. Replaces the PR2 A6 interim
  "None (cwd: ...)" override.

- **`wise plot` group** (F4.1): `wise plot features NAME SCALES`
  (kinematic distance-from-core vs. epoch), `wise plot links NAME
  SCALES` (feature trajectories on the reference map), `wise plot sep
  NAME SCALES` (separation-from-core vs. time). Options and arguments
  are unchanged from the old top-level commands.

- **`wise show` group** (F4.2): `wise show features NAME SCALES`
  (feature locations on the reference image), `wise show image FILES`
  (simple image viewer), `wise show info FILES` (beam/pixel/epoch
  table). Options and arguments unchanged.

- **`<name>.wiseproj/` result bundles** (F5): saved results are now a
  single directory with generic file names — `manifest.json`,
  `detection.dat`, `image_set.dat`, `config.wise_config`, and one
  `links_<scale>.dfc.dat` per scale that has links. `manifest.json`
  carries `schema_version` ("1.0"), the result name, the writing
  `wise_version`, an ISO-8601 `created` timestamp, and a `files` map
  the loader uses to locate the data files. The manifest is written
  last, so a bundle missing it is detectably incomplete. Saving onto an
  existing bundle raises a UsageError rather than overwriting.

### Changed (BREAKING)

- **CLI surface regrouped** (F4): the chart/render/table commands moved
  under the `wise plot` and `wise show` groups (see Added). The old
  top-level spellings are removed (see Removed). Update scripts:
  `wise plot_features` → `wise plot features`, `wise view_links` →
  `wise plot links`, `wise plot_sep_from_core` → `wise plot sep`,
  `wise view_features` → `wise show features`, `wise view` →
  `wise show image`, `wise info` → `wise show info`.

- **Saved-result layout** (F5): `wise` 1.0 reads and writes only the
  `<name>.wiseproj/` bundle layout; the 0.5/0.6
  `<name>/<name>.set.dat` layout is no longer read or written.
  Loading a name that still exists in the old layout raises a
  UsageError pointing at `wise upgrade-config` (coming in PR8). To keep
  using old result directories in the meantime, install
  `wisetool==0.6.*`. The migration tool itself lands in PR8.

### Removed (BREAKING)

- **`wise info --project` flag** (F4.3): absorbed into the new
  `wise project` command (see Added). `wise info` itself is removed in
  favor of `wise show info`.

- **Old top-level CLI commands** (F4.4): `wise plot_features`,
  `wise plot_sep_from_core`, `wise view`, `wise view_features`,
  `wise view_links`, and `wise info`. No migration stubs — click's
  "no such command" error is the feedback path. The replacements live
  under the `wise plot` / `wise show` groups (see Changed). The six
  matching PR1 importable-but-empty `actions/wise_*.py` shim modules
  are removed as well.

- **`data.data_dir` from `DataConfiguration`** (F3.3). The project
  root, resolved by walking upward from cwd for a `.wise/` directory,
  is now the sole source of truth for "where is this project's data."
  `AnalysisContext.get_data_dir()` no longer falls back to
  `os.getcwd()`; it raises `wise.ProjectRootNotFound` (a
  `click.UsageError` subclass) when no project root is found.
  **Migration:** run `wise init` in the directory that previously held
  your `wise_config`. The full upgrade path for 0.5/0.6 projects
  (including key renames and result-directory migration) lands in PR8
  as `wise upgrade-config`.

- **A2 interim `display_overrides` hook** on
  `wise settings show` / `doc` (`_data_dir_overrides` in `cli.py`).
  Superseded by the new "Project root:" header now that `data_dir` is
  gone. The `display_overrides=` kwarg on
  `BaseConfiguration.values()` is retained — F6 in PR10 will reuse it
  for the docs-site reference page.

## [0.6.0] — 2026-05-23

The "everything got nicer; nothing got harder" release. Phase 1 of the
wise 1.0 plan, sequenced in `_wise_1_0_roadmap.md` (PRs #16, #17, #18,
#19). Migrates the CLI to `click`, replaces `print()` status output
with structured logging, unifies the settings table, makes silent
failures loud, and adds per-knob doc-string guidance plus a
`wise detect --dry-run` preview for empirical α-threshold tuning. **No
breaking changes** — 0.5.0 configs and saved result directories
continue to work as-is. The 1.0 breaking changes (the
`--nsigma_connected` rename, the `alpha_threashold` typo fix,
subcommand regrouping, the project-root resolver, the new result
directory layout) are deferred to v1.0.0; users who need to stay on
the pre-click CLI can pin `wisetool==0.5.*` or track the `0.5.x`
maintenance branch.

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
  library warnings through the same handler.

- **CliRunner smoke tests** (F7 baseline): `packages/wise/tests/
  test_cli_smoke.py` — covers `--help` on every subcommand,
  `--version`, verbosity mutual-exclusion, a non-interactive no-files
  clean-exit check, and the unified settings table format from PR2.

- **Unified settings table** (A1): `wise settings show` now renders a
  single 6-column table — `Option | Value | Default | Unit | Range |
  Documentation` — for every configuration section.

- **Unit metadata** (A1): `DataConfiguration`, `FinderConfiguration`,
  and `MatcherConfiguration` carry a new `unit` field on every
  settings tuple. Notable values: `bg_coords` / `roi_coords` → `"mas
  (= data.projection_unit)"`, `alpha_threashold` / `alpha_detection`
  → `"σ"`, `min_scale` / `max_scale` → `"wavelet level (int 0–10)"`,
  `object_z` → `"redshift"`. Callers that subclass
  `BaseConfiguration` with 7-element tuples continue to work (the
  missing `unit` is padded with `None` at init time).

- **Validator range descriptions** (A1): Every validator factory
  (`validator_in_range`, `validator_in`, `validator_is`,
  `validator_is_class`, `validator_list`, `is_callable`) now exposes a
  `.describe()` method so the settings table can show a human-readable
  Range column. `validator_in_range` also exposes `.min` and `.max`.

- **`wise settings show data.data_dir` cwd note** (A6 interim): When
  `data.data_dir` is `None`, the Value cell now reads `"None (cwd:
  <abs-path>)"` instead of bare `None`, making the cwd fallback
  explicit. Full project-root resolution is deferred to v1.0.0.

- **Projection-unit headers in `wise info`** (E3): The "Pixel scale"
  and "Beam" columns in the `wise info` table now include the
  projection unit in their header (e.g. `"Pixel scale (mas)"`,
  `"Beam (mas)"`). Changing `data.projection_unit` updates the headers
  automatically.

- **Save-path echo in `wise detect` / `wise match`** (E4): After
  saving a result, both commands now print `"Saved to <abs-path>/"`
  so users know exactly where the output landed.

- **Truncation indicator in `format_table`** (E2): When a cell value
  has no whitespace within `max_col_size` (e.g. a jsonpickle-encoded
  callable), it is now truncated to the column width and the final
  character is replaced with `…` instead of being silently cut.

- **`AnalysisConfiguration.validate()`** (B3): extensible registry of
  `(check_fn, message)` pairs on `_CHECKS`. Returns a list of
  human-readable issue strings when the configuration is inconsistent.
  The first check flags the case where no background-extraction method
  is configured (`bg_coords`, `bg_use_ksigma_method`, and `bg_fct` are
  all unset). Future PRs can append checks without touching the
  method structure.

- **Per-scale pixel-width footer under `wise settings show finder`** (C1):
  After the finder table, a `Resulting widths: […] px  (wavelet=…,
  use_iwd=…)` line shows the actual pixel feature widths that wavelet
  detection will see at each decomposition level. Computed from
  `min_scale`, `max_scale`, and the configured wavelet family
  (b3/triangle2 use a 1.5× larger multiplier than b1/etc). Also
  appears in `wise settings show` (all sections), positioned
  immediately after the finder table. When `use_iwd=True`, both
  wavelet names are shown (e.g. `wavelet=b1+b3, use_iwd=True`). The
  underlying helper is `wise.wds.compute_scales_widths(min_scale,
  max_scale, wavelet)` — callable from notebooks.

- **`wise detect --dry-run`** (C2): Previews detection on a single
  input file without running segmentation, saving, or the view-scales
  loop. Prints a per-scale table of `Scale (level) | Width (px) |
  σ_noise | Above α=<current> (current) | Between α=1.5 and
  α=<current>` to help users tune `finder.alpha_detection`
  empirically. Requires exactly one input file. Analytics are
  factored into `wise.tasks.detection_preview(ctx, file,
  alpha_lower=1.5)`, which returns a list of per-scale stat dicts
  and is callable from notebooks.

### Changed

- `libwise.scriptshelper` is no longer imported by any
  `wise.actions.wise_*` module. The libwise standalone scripts
  (`wt-denoise`, `wt2d`, `fits-crop`) and `wise/contrib/` modules
  still use it; it is not deleted.

- `wise select_files --end-date` short option is `-e` (corrected from
  the old `-d` USAGE string, matching the original code behaviour).

- **Per-knob doc-string guidance for 7 config knobs** (C2): The
  `Documentation` column in `wise settings show` now carries
  actionable guidance for:
  - `finder.alpha_threashold` — explains its role in the watershed
    mask and the relationship to `alpha_detection`.
  - `finder.alpha_detection` — names the default-vs-diffuse-source
    trade-off and points to `wise detect --dry-run` for empirical
    tuning.
  - `finder.min_scale` and `finder.max_scale` — clarify that values
    are wavelet *levels*, not pixels, and point to the new
    `Resulting widths` footer for the pixel equivalents.
  - `data.projection_unit` — explains the VLBI default and when to
    switch to `arcsec` for connected-element data.
  - `data.object_z` — describes its cosmology role and the
    precedence rule with `object_distance`.
  - `data.object_distance` — describes the expected Quantity format
    and its precedence over `object_z`.

### Fixed

- **`bg_coords` clamp warning** (B1): `AnalysisContext.get_bg` now
  emits a `WARNING` when `nputils.clamp` changes any coordinate, so
  users can see that their background region was trimmed to the image
  edge and the noise estimate may be affected.

- **Resolved background pixel slice** (B7): `get_bg` always logs the
  resolved pixel slice at `INFO` level (`Background region: pixels
  x=[…:…] (… px), y=[…:…] (… px)`). Visible under `wise -v`; silent
  at the default `WARNING` level. Lets users catch twisted or
  non-opposite-corner `bg_coords` inputs.

- **`core.dat` epoch mismatch warning** (B2):
  `CoreOffsetPositions.align_img` previously did nothing when an
  image's epoch was absent from `core.dat`, silently leaving the
  image unaligned. It now emits a `WARNING` naming the missing
  epoch so the user can diagnose noisy proper-motion results.

- **Background-method validation at config-load time** (B3):
  `actions.get_config` calls `config.validate()` after loading and
  emits a `WARNING` for each issue. `wise settings show` and
  `wise settings doc` append a `⚠ Configuration issues:` banner
  below the table when issues are present. Users see the problem
  on every `wise` invocation until they fix the config; `--quiet`
  suppresses.

- **`_resolve_optional_file` helper** (B4): introduces
  `AnalysisContext._resolve_optional_file(attr_name)` which returns
  the absolute path of an optional config-named file if it exists
  on disk, else `None`. `get_core_offset`, `get_mask`,
  `get_stack_image`, and `select_files` route through this helper,
  eliminating `os.path.isfile(None)` crash paths. `save_mask_file`
  now raises `ValueError` when `data.mask_filename` is unset, and
  guards the existing-file removal with `if filename and
  os.path.isfile(…)`.

- **Input glob skips mask/ref/stack files** (B6):
  `AnalysisContext.select_files` now filters out files whose
  absolute path matches `data.mask_filename`,
  `data.ref_image_filename`, or `data.stack_image_filename`,
  logging a `WARNING` for each skip. This prevents `wise detect
  *.fits` from running detection on the mask or stacked output
  when those files live in the same directory.

- **`astropy FITSFixedWarning` suppressed** (E5): `_setup_logging`
  in the CLI entry point adds
  `warnings.filterwarnings("ignore", category=FITSFixedWarning)`
  to silence the four-lines-per-file FITS-spec drift spam. Other
  astropy warnings (`VerifyWarning`, etc.) still flow through.

- **"Applying preset" banner** (E1): `RcPreset.apply()` previously
  printed `"Applying preset: display"` on every command
  invocation. This is now routed through `logger.debug()` and only
  appears under `wise --debug`.

- **`save_core_offset_pos_file` None guard**: when
  `data.core_offset_filename` is `None`, the method now raises
  `ValueError("data.core_offset_filename is not set; cannot save
  core offset positions.")` before attempting the write. Parallels
  the `save_mask_file` guard.

- **`get_stack_image` error message**: upgraded the bare
  `Exception("A stack image need to be generated")` to
  `RuntimeError("No stack image found; run` `wise stack <files>`
  `first to generate one.")`. Exception class matches the
  silent→loud pattern; message tells the user exactly what to do.

- **Stale shim comments in `wise_detect`, `wise_info`, `wise_match`,
  `wise_stack`**: the `"; the wise_<name>.main() shim below is dead
  code"` clause was left in the module-level comments after the
  click migration but the shims were removed. Comments now read
  simply: `# CLI entry point migrated to wise.cli (click). This
  module is kept for importability.`

### Deprecated

- `wise settings doc` is deprecated; it now produces the same
  output as `wise settings show`. It will be removed in wise 1.0.

### Removed

- **`packages/wise/scripts/wise`**: orphan Python 2 dispatch script
  using bare `print` statements (syntactically broken since the Py3
  port). The working CLI entry point is `wise.cli:main` registered
  via `[project.scripts]` in `pyproject.toml`; this file had no
  effect on installs.

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
