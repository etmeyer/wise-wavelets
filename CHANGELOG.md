# Changelog

All notable changes to wise-wavelets are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Two commands for maps that weren't made with wise in mind, from the
J1304-2106 astrogeo X-band analysis: `wise core` measures core
positions and writes the core offset file, and `wise prep` puts maps
from different arrays or pipelines on one pixel grid with the core on
the reference pixel. Alignment on a core offset file is now sub-pixel
by default, which moves results on existing projects slightly (see
Changed).

### Added

- **`wise core FILES`** fits each map's core with a Gaussian of the
  restoring-beam shape (free in peak and position) and writes the core
  offset file (`data.core_offset_filename`), in
  `data.projection_unit`. It prints each core's position, formal
  error and SNR, with a free-shape fit as a check for a resolved or
  blended core. `--search-radius` and `--near` pick the component when
  the core isn't the brightest pixel near the reference pixel;
  `--dry-run` only prints, and an existing file is replaced only with
  `--overwrite`.

- **`wise prep FILES -o DIR`** resamples each map onto one grid (by
  default the finest input pixel over the smallest input field), with
  its core on the reference pixel, so that maps from different grids
  can go through `detect`, `match` and `stack`. Maps with an AIPS CC
  table are restored from their clean components on the new grid and
  only the residual is interpolated; maps without one are
  interpolated. `--beam native|common|BMAJ,BMIN,PA` keeps each map's
  beam, uses the smallest beam that contains them all, or uses the
  given one. Headers record the input file and offset (`ORIGFILE`,
  `PREP_DX`, `PREP_DY`, `PREP_CEN`, `HISTORY`), and `prep_log.txt`
  in `DIR` lists what was done. `--no-center` only regrids. Maps that
  `wise prep` centered are not aligned on a core offset file, so one
  measured on the input maps can't shift them a second time. The
  formats are in *Data file formats* in the docs.

- **`data.align_subpixel`** (default `true`): align images on the
  core offset file by the exact offset, interpolating with a cubic
  spline.

- Python API: the `wise.prep` module (`Beam`, `common_beam`,
  `fit_core`, `prepare_map`, `prepare_files`, …),
  `FitsImage.get_clean_components()`, and a `subpixel` argument to
  `Image.shift` and `CoreOffsetPositions.align_img`.

### Changed

- **Core-offset alignment is sub-pixel by default.** wise 1.0 rounded
  each shift to whole pixels, so on an existing project each epoch
  moves by up to half a pixel along each axis, and fitted velocities
  change accordingly. Set `data.align_subpixel = false` to reproduce
  1.0.

### Fixed

- **Images from the same day are refused up front**: `detect`,
  `match`, `stack` and `bootstrap_matching`, like the new `wise core`
  and `wise prep`, stop before any work with an error listing the
  images of each shared day. `detect` and `match` crashed with a bare
  `AssertionError` after detecting the earlier epochs,
  `bootstrap_matching` overwrote one image's detections with the
  other's, and images a few hours apart passed every check. Days are
  compared, so astrogeo's `(2)` second observations count. New:
  `AnalysisContext.check_unique_epochs()` and `DuplicateEpochError`.

- **Core offset rows match images by day**: an image whose DATE-OBS
  has a time of day was left unaligned, with a "No core position"
  warning, because rows are stored by date only.

- **A core offset file with a single row loads**; it raised a
  `ValueError`.

## [1.0.1] — 2026-10-27

A bug-fix release, for problems found while running wise on the
astrogeo X-band maps of J1304-2106 (#12). Commands, settings and file
formats are unchanged, and 1.0.0 projects need no migration. Two fixes
can change what an existing project does: epochs whose DATE-OBS ends
in a `(N)` counter are no longer dropped, and images on different
pixel grids now stop `detect`, `match` and `stack` with an error
instead of giving wrong positions.

### Fixed

- **DATE-OBS with a trailing counter is parsed** (#12): astrogeo maps
  carry values like `'2015-09-28(2)'`, and those epochs were dropped
  with a "could not be parsed" warning. Both date readers now strip a
  trailing `(N)`. A missing DATE-OBS no longer raises a bare
  `Exception` from the fast header reader (the file is skipped with
  the usual warning), and a DATE-OBS past the reader's 100-card window
  is found through astropy.

- **Clear errors for unusable input** (#12): commands that take FILES
  now stop with a usage error when a path doesn't exist (an unmatched
  shell glob used to end in a `FileNotFoundError` traceback) or when no
  file survives selection (`wise show info` used to crash with an
  `IndexError`, and `wise detect` / `wise match` returned silently).
  File lists given as a text file may contain blank lines.

- **Images on different pixel grids are refused**: `wise detect`,
  `wise match`, `wise stack` and `bootstrap_matching` stop with an
  error listing each grid and its files, instead of running silently,
  crashing on a numpy broadcast error, or stacking mismatched pixels.
  The reference image is checked too, except when building a stack.
  The matcher measures displacements in pixels, so mixed grids gave
  wrong positions and velocities. New:
  `AnalysisContext.check_common_grid()` and `GridMismatchError`.

- **`wise show info` beam and date columns**: the beam is printed as
  `Bmaj x Bmin, PA` with the PA in degrees (it was `Bmin, Bmaj` with
  the PA in radians), the unit appears only in the header, and dates
  no longer carry `00:00:00`. `Image.get_epoch(str_format)` now
  formats dates and datetimes with the format it is given. The
  `--velocity` table prints rounded values.

- **astropy `VerifyWarning` is silenced in the CLI**, next to the
  existing `FITSFixedWarning` filter. astrogeo's non-standard
  RA/DEC/PROJECT/URL cards produced about ten lines of warnings per
  file.

- **Finder widths footer with `use_iwd`**: `wise settings show finder`
  now lists the intermediate scales too (e.g. `[8, 12, 16, 24, 32,
  48] px` for min_scale=3, max_scale=6, where it showed
  `[8, 16, 32]`).

- **`wise detect --dry-run` previews what detection sees**: the image
  gets the core alignment and ROI crop, peaks outside the mask are not
  counted, and the first column shows the wavelet level and family
  (e.g. `3 (b1)`, `3 (b3)`) instead of a 1-based index labelled as the
  level. `detection_preview()` adds `level` and `wavelet` keys.

- **`data.object_distance` help text**: it is an angular-diameter
  distance, not a luminosity distance. Speeds are angular speed x
  distance x (1 + `object_z`), so following the old text overstated
  them by (1 + z), or (1 + z)^2 with `object_z` also set. The
  `object_z` text now names the cosmology (WMAP9).

- **Docs install page**: it still gave the original Python 2
  instructions (`conda install -c flomertens` or `pip install
  wisetool`), which install the 0.4.7 release. It now gives this
  repository's conda and pip instructions. The docs also read their
  version from the `wise` package; they showed 0.1.

### Added

- **Test workflow** (`.github/workflows/tests.yml`): runs the test
  suite on pushes to `main` and on pull requests, in the conda
  environment from `environment.yml`.

## [1.0.0] — 2026-06-25

The clean-break release. wise 1.0 introduces a project-root concept
(`wise init` and a `git`-style upward resolver, sole source of truth
for "where is this project's data"), regroups the CLI into `wise plot`
and `wise show` subcommand families, restructures saved results into
self-describing `<name>.wiseproj/` bundles with a `manifest.json`, and
takes the long-overdue breaking renames (`alpha_threashold` →
`alpha_threshold`, `--nsigma_connected` → `--keep_brightest_only`).
Loading or interpreting 0.5/0.6-shaped projects in 1.0 is no longer
supported.

**Migration path:** install 1.0, `cd` into your existing 0.5/0.6
project, and run `wise upgrade-config --dry-run .` to preview, then
`wise upgrade-config .` to apply. The migrator rewrites
`wise_config`, converts old `<name>/<name>.set.dat` directories into
`<name>.wiseproj/` bundles, creates the `.wise/` marker, and is
idempotent.

**Escape hatches for users who can't migrate yet:**
`git checkout v0.6.0` (the immediate predecessor, same CLI surface
as 0.5 but with the v0.6.0 polish) or `git clone --branch 0.5.x
https://github.com/etmeyer/wise-wavelets` (the long-lived
upstream-compatible maintenance branch).

**Known limitation:** saved detections cannot be re-matched in 1.0
— the bundle persists feature centroids only, not the segment pixel
data the default matcher needs. `wise match` always re-runs
detection. The primary fix (extending the bundle) is tracked for a
future v1.x release.

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

- **`wise.project.decode_scale_dict`** (C4, C5): a lenient decoder for
  config dicts keyed by wavelet scale. Accepts both Python-literal form
  (`{4: 4.0}`, int/float keys) and JSON form (`{"4": 4.0}`, string
  keys), normalizing keys to `int` for pure integers and `float`
  otherwise. Wired into `finder.scales_snr_filter` and
  `matcher.min_scale_tolerance`, whose downstream lookup is by numeric
  scale and so silently missed the JSON string keys users were forced
  to write. The encoder stays `jp.encode` (portable string-keyed JSON);
  only the decode path is lenient, and the encode→decode round-trip
  yields an equal int-keyed dict.

- **`libwise.nputils.OptionRenamedError`** + `BaseConfiguration`
  `_RENAMED_OPTIONS` hook: a subclass populates `_RENAMED_OPTIONS =
  {old_key: new_key}` so that accessing a renamed option raises
  `OptionRenamedError` (carrying `.old_name` / `.new_name`) instead of
  a bare `AssertionError`. Unknown (non-renamed) options still raise
  `AssertionError`. libwise stays click-free; the wise layer catches
  this and re-raises a `click.UsageError` with a migration hint.

- **`wise upgrade-config [DIRECTORY]`** (PR8): one-shot migration from
  the 0.5/0.6 layout to 1.0. Rewrites `wise_config` (renames
  `alpha_threashold` → `alpha_threshold`, drops the removed `data_dir`,
  leaves everything else untouched), converts each
  `<name>/<name>.set.dat` result directory into a `<name>.wiseproj/`
  bundle with the 1.0 file names and a fresh `manifest.json`, creates
  the `.wise/` project marker, and appends `.wise/` to an existing
  `.gitignore`. Idempotent — re-running is a no-op — and `--dry-run`
  previews every change without writing. Both 0.6.0 link-file spellings
  (`<name>_<scale>.dfc.dat` and the `.ms.dfc.dat` that 0.6.0 actually
  wrote) are recognized. The migrator is a self-contained, stdlib-only
  module (`wise.upgrade`) so it can later be backported to a 0.6.x
  forward-migration shim.

### Changed (BREAKING)

- **`--nsigma_connected` → `--keep_brightest_only`** (A4): the `wise
  stack` flag is renamed; the misleading old name read as "keep all
  connected blobs above σ" but meant "keep only the brightest blob".
  The `-c` short option is preserved. Passing the old flag errors with
  a clear rename message (a hidden migration callback, not click's
  generic "no such option"). The Python API renames to match:
  `AnalysisContext.build_stack_image` / `get_stack_image` and the
  `set_stack_image_as_ref` / `set_mask_from_stack_img` / `view_stack`
  task helpers now take `keep_brightest_only`.

- **`alpha_threashold` → `alpha_threshold`** (C3): the misspelled
  finder config key is fixed. Loading a `wise_config` that still uses
  the old spelling raises a `click.UsageError` naming both keys and
  pointing at `wise upgrade-config`. No alias — clean break.

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
  UsageError pointing at `wise upgrade-config`. To keep using old
  result directories without migrating, check out the `v0.6.0` tag
  or the `0.5.x` branch.

### Changed

- **`wise match` re-detect notice** (A2): `wise match` now prints a
  notice on every invocation (suppressible with `--quiet`) that it
  re-runs detection with the current `finder.*` settings before
  matching, and that 1.0 `.wiseproj` bundles save feature centroids
  only — so a saved detection cannot be re-matched in this release (see
  Known limitations). The `wise detect` save prompt is reworded to
  "Save detection for plotting only? (1.0 bundles cannot be
  re-matched.)" and the `wise match` save prompt to "Save matched
  result?", so the save dialog no longer implies a reusability that
  does not exist.

### Known limitations

- **Saved detections cannot be re-matched** (A2): a `.wiseproj` bundle
  persists feature centroids only, not the segment pixel data the
  default correlation matcher needs. `wise match <name>` therefore
  cannot load a saved detection and run only the matcher; it re-runs
  detection from the input FITS with the current `finder.*` config.
  The primary fix (extending the bundle to carry enough detection state
  to re-match) is tracked for a future v1.x release.

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
  **Migration:** run `wise upgrade-config` (which creates `.wise/`
  alongside the key/layout rewrites), or `wise init` if you only need
  the marker.

- **A2 interim `display_overrides` hook** on
  `wise settings show` / `doc` (`_data_dir_overrides` in `cli.py`).
  Superseded by the new "Project root:" header now that `data_dir` is
  gone. The `display_overrides=` kwarg on
  `BaseConfiguration.values()` is retained — F6 in PR10 will reuse it
  for the docs-site reference page.

### Fixed

- **Non-integer per-scale link files now load** (PR7 drive-by):
  `MultiScaleFeaturesLinkBuilder.from_file` used a `[0-9]+` scale regex
  that silently skipped per-scale link files at non-integer scales —
  a real failure mode given PR4's wavelet-width formula produces floats
  like 1.5 and 4.0. The pattern is now `[0-9.]+` with a properly
  escaped suffix, so links at non-integer scales load.

- **`list_saved_results` no longer crashes on call** (PR7 drive-by):
  it referenced an undefined `stack_img` where `ref_img` was meant —
  a `NameError` on every invocation. Fixed.

- **Bundle config snapshot is found on load** (PR7 drive-by): a
  `.conf` vs `.config` filename mismatch between the writer
  (`tasks.save`) and the reader (`actions.load`) meant the saved config
  snapshot could never be located. The bundle now uses a single
  `config.wise_config` name for both.

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
