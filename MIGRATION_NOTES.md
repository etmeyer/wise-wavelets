# Migration notes

A running log of every non-mechanical substitution made during the Python 2 → 3
port of `libwise` and `wise`. See `MIGRATION_PLAN.md` for the overall plan.

## Phase 3 — pymorph → scikit-image

`pymorph` was abandoned and Python 2-only. Phase 3 replaced every call site
with a scikit-image equivalent. Across both packages there was exactly one
call site, plus the import.

| File | pymorph call | skimage replacement | Notes |
| --- | --- | --- | --- |
| `packages/libwise/src/libwise/nputils.py` (~L97) | `pymorph.secross(r=int(size))` | `skimage.morphology.diamond(int(size))` | `secross` was not in the migration plan's mapping table — it isn't one of the named pymorph entry points the plan anticipated. `pymorph.secross(r=N)` is defined as `N`-fold dilation of the basic 4-connected cross structuring element, which produces the L1-ball footprint `{(i,j) : |i| + |j| ≤ N}`. That's exactly `skimage.morphology.diamond(N)`. The result feeds into `scipy.ndimage.grey_dilation(signal, footprint=…)` in `find_peaks` (~L957); `grey_dilation` accepts `footprint` as either bool or integer arrays, so the dtype difference between pymorph (uint8) and skimage (uint8 in current versions) is irrelevant here. No other call sites consume the cached footprint, so no boundary cast was needed. |

### Other Phase 3 mapping entries — unused

The plan listed mappings for `pymorph.dilate`, `erode`, `open`, `close`,
`label`, `regmin`, `regmax`, `gradm`, `thin`, `sebox`, and `sedisk`. None of
these appeared in the codebase — `secross` was the only function the
upstream actually called. The label-unpacking and gradm-footprint hazards
the plan flagged therefore did not materialize.

### Documentation cleanup

`packages/libwise/README.md` and `packages/wise/README.md` listed `pymorph`
in their Py2-era Requirements sections. Removed both lines so the Phase 3
verify (`grep -rn "pymorph" packages/`) returns zero. Phase 7 will rewrite
these READMEs in full to point at `environment.yml` / `pyproject.toml` as
the source of truth for dependencies.

## Phase 4 — numpy 2.x / skimage / matplotlib / pyregion / astropy drift

`import libwise, wise` now succeeds against the conda env (numpy 2.4,
scipy 1.16, scikit-image ≥0.22, matplotlib ≥3.9, astropy ≥6, pyregion 2.2,
PyQt5 5.15, Python 3.11). The substitutions follow.

### numpy 2.x — bare scalar aliases

The plan's table covered the `np.<name>_` aliases (`np.float_`, etc.)
removed in numpy 2.0. Those didn't appear in the codebase. What did appear
were the older bare aliases (`np.int`, `np.float`, `np.complex`) which
numpy deprecated in 1.20 and removed in 1.24 — also gone in our env. The
upstream alias was a thin wrapper around the Python builtin (`np.int` was
literally `int`, not `np.int_`/`np.intp`), so the like-for-like substitute
is the Python builtin. All call sites are dtype/cast use, where `int`,
`float`, `complex` resolve to the platform default integer / `float64` /
`complex128` exactly as the alias did.

| File | Old | New |
| --- | --- | --- |
| `packages/libwise/src/libwise/imgutils.py` (~L117, L1741) | `dtype=np.int` | `dtype=int` |
| `packages/libwise/src/libwise/imgutils.py` (~L178) | `x.astype(np.complex)` | `x.astype(complex)` |
| `packages/libwise/src/libwise/imgutils.py` (~L459-460) | `dtype=np.float` | `dtype=float` |
| `packages/libwise/src/libwise/plotutils_ui.py` (~L257) | `y.astype(np.int), x.astype(np.int)` | `y.astype(int), x.astype(int)` |
| `packages/libwise/src/libwise/nputils.py` (~L1095) | `.astype(np.int)` | `.astype(int)` |
| `packages/libwise/src/libwise/nputils.py` (~L1865) | `np.int(np.ceil(...))` | `int(np.ceil(...))` |
| `packages/libwise/src/libwise/nputils.py` (~L1931) | `if not n.dtype == np.int:` | `if not n.dtype == int:` (numpy compares dtype against `int` by resolving to the platform default integer dtype, matching the original semantics where `np.int` *was* `int`) |
| `packages/libwise/tests/test_imgutils.py` | `(res * 1000).astype(np.int)` | `(res * 1000).astype(int)` |
| `packages/wise/src/wise/tasks.py` (~L1079) | `.astype(np.float)` | `.astype(float)` |
| `packages/wise/src/wise/matcher.py` (~L1497, L1781) | `.astype(np.int)` | `.astype(int)` |
| `packages/wise/src/wise/wds.py` (~L320) | `.astype(np.int)` | `.astype(int)` |

Commented-out occurrences in `matcher.py` and `nputils.py` were also
updated so the verify grep is unconditionally clean.

### scikit-image — watershed move (Phase 4 plan §"scikit-image")

| File | Old | New |
| --- | --- | --- |
| `packages/wise/src/wise/wds.py:2` | `from skimage.morphology import watershed` | `from skimage.segmentation import watershed` (moved in scikit-image 0.19) |

`selem=` keyword renames and `regionprops` dict-like access — neither
pattern occurs in the codebase. The plan flagged them defensively; nothing
to do.

### matplotlib — backend rename, removed mlab fn, removed AnchoredEllipse

| File | Old | New |
| --- | --- | --- |
| `packages/libwise/src/libwise/plotutils_ui.py` (~L19-20) | `matplotlib.backends.backend_qt4agg` | `matplotlib.backends.backend_qt5agg` (rename in PyQt4 fallback branch; PyQt4 widget porting is Phase 5) |
| `packages/libwise/src/libwise/app/PolyRegionEditor.py` (~L31) | `from matplotlib.mlab import dist_point_to_segment` | inlined a 6-line numpy implementation (point-to-segment distance with endpoint clamping); the upstream function was removed from `matplotlib.mlab` |
| `packages/libwise/src/libwise/plotutils_base.py` (~L28, L182) | `from mpl_toolkits.axes_grid1.anchored_artists import AnchoredEllipse` | `AnchoredEllipse` was removed in matplotlib 3.8. Inlined the deprecated upstream class verbatim (subclass of `AnchoredOffsetbox` wrapping an `Ellipse` in an `AuxTransformBox`). The plan didn't anticipate this — picked it up at import time. |

`matplotlib.mlab.csd` and `detrend_mean` (used in `nputils.test_upsample`)
are still present in matplotlib ≥3.7; left as-is.
`matplotlib.backends.qt_editor.figureoptions` (the `figure_edit` entry
point in `plotutils_ui.py`) still exists in matplotlib ≥3.7 — Phase 5
will cover any Qt-time API drift if it surfaces.

### pyregion — no changes needed

`pyregion.open(...)`, `ShapeList` iteration, `shape.name` / `shape.attr` /
`shape.coord_list`, and `ShapeList.as_imagecoord(header)` are all still
present in pyregion 2.2. No patches required at this phase. (If the Qt
editor pipeline turns up a drift later, patch in place — the plan's
deferred-refactor-to-`regions` decision still stands.)

### astropy — no changes needed

`astropy.units`, `astropy.wcs`, `astropy.io.fits`, `astropy.cosmology`
(only ever called via `default_cosmology.set(...)` — no setattr on a
constructed cosmology object), and `astropy.time.TimeDelta` (only used in
`isinstance` checks) are all stable. No patches required.

### Phase-2 leftover — `from scipy.ndimage import measurements`

Phase 2's verify grep used `scipy\.ndimage\.measurements`, which only
matched dotted-attribute access (`scipy.ndimage.measurements.X`) — it
didn't catch the `from scipy.ndimage import measurements` form. Three
files used the latter; modern scipy still ships the `measurements`
namespace as a deprecated re-export, but it's gone in scipy 1.14+.
Replaced now since the verify wasn't strict enough on the Phase 2 commit.

| File | Old | New |
| --- | --- | --- |
| `packages/libwise/src/libwise/plotutils_base.py:8` | `from scipy.ndimage import measurements` | deleted (the import was unused) |
| `packages/libwise/src/libwise/plotutils_ui.py` (~L472) | `measurements.center_of_mass(data)` | `ndi.center_of_mass(data)` (added `from scipy import ndimage as ndi`) |
| `packages/wise/src/wise/wds.py:3` | `from scipy.ndimage import measurements, gaussian_filter` | split into `from scipy import ndimage as ndi` + `from scipy.ndimage import gaussian_filter`; rewrote 5 `measurements.X` call sites to `ndi.X` |
| `packages/wise/src/wise/wiseutils.py:18` | `from scipy.ndimage import measurements` | `from scipy import ndimage as ndi`; rewrote 2 `measurements.center_of_mass` call sites to `ndi.center_of_mass` |

### `pkg_resources` → `importlib.resources`

Setuptools 81 (May 2025) dropped `pkg_resources` from the default install,
so `import pkg_resources` raises `ModuleNotFoundError` against the conda
env. The plan flagged this as optional cleanup; with the env unable to
import it became a blocker, so migrated the four call sites to
`importlib.resources` (stdlib since 3.9). The replacements are like-for-like:

| File | Old | New |
| --- | --- | --- |
| `packages/libwise/src/libwise/imgutils.py` (~L17, L208) | `pkg_resources.resource_stream(__name__, GALAXY_GIF_PATH)` | `resources.files(__package__).joinpath(GALAXY_GIF_PATH).open('rb')` (used inside a `with` block; opens the bundled GIF for `PIL.Image.open`) |
| `packages/libwise/src/libwise/presetutils.py` (~L8, L38, L193) | `pkg_resources.resource_listdir(__name__, 'presets')` and `resource_stream(__name__, ...)` | `resources.files(__package__).joinpath('presets').iterdir()` (then `.name`) and `.joinpath('presets', file_name).open('r')` |
| `packages/libwise/src/libwise/plotutils_ui.py` (~L1, L681) | `pkg_resources.resource_string(imgutils.__name__, name)` | `resources.files(imgutils.__package__).joinpath(name).read_bytes()` |

Note the `__package__` switch: `pkg_resources.resource_*` accepts a fully
qualified module name (matching `__name__`), whereas
`importlib.resources.files` expects a package name. Inside a package
`__init__.py` they're the same, but inside a submodule (which all three
of these are) they differ — `__package__` is the right spelling.

## Phase 5 — Qt UI port to PyQt5

Six files exercised Qt: `uiutils.py`, `plotutils_ui.py`,
`waitingspinnerwidget.py`, `app/PolyRegionEditor.py`,
`app/waveletsui.py` (the rest of `app/*.py` use only
`uiutils`/`plotutils` indirection). All three import lines from the plan
now succeed against the conda env:

```
python -c "from libwise.app import PolyRegionEditor, WaveletBrowser, WaveletDenoise"
python -c "from libwise.app import WaveletTransform, WaveletTransform2D"
python -c "from libwise.app import WaveletFilterResponse, Wavelet2DBrowser, waveletsui"
```

### Drop the PyQt4 fallback + setattr shim

Upstream's pattern was a two-branch import: try PyQt5, copy every
`QtWidgets.X` into `QtGui` via `setattr` so existing `QtGui.QWidget`
call sites keep working; otherwise fall back to PyQt4 (where widgets
already lived under `QtGui`). The shim worked but polluted the `QtGui`
namespace and left every call site ambiguous about which module it
*should* be hitting. Phase 5 swaps the four shim sites for a clean
`from PyQt5 import QtCore, QtGui, QtWidgets` and qualifies each call
site explicitly. The mapping is the standard Qt4→Qt5 split: `Q*` widget
classes (`QApplication`, `QWidget`, `QFileDialog`, `QPushButton`,
`QLabel`, `QLineEdit`, `QComboBox`, `QSpinBox`, `QSlider`,
`QMessageBox`, `QInputDialog`, `QBoxLayout`/`QVBoxLayout`/`QHBoxLayout`,
`QFormLayout`, `QTabWidget`, `QTreeView`, `QStackedWidget`,
`QScrollArea`) → `QtWidgets`; graphics primitives (`QFont`,
`QFontMetrics`, `QIcon`, `QImage`, `QPalette`, `QPixmap`) stay in
`QtGui`; `QtCore` is unchanged.

### Qt5-specific moves not in the standard mapping

| Class | Qt4 location | Qt5 location | Affected file |
| --- | --- | --- | --- |
| `QSortFilterProxyModel` | `QtGui` | `QtCore` | `plotutils_ui.py::TreeQSortFilterProxyModel` (was patched at import via `QtGui.QSortFilterProxyModel = QtCore.QSortFilterProxyModel`; subclassing now spells `QtCore.QSortFilterProxyModel` directly) |

`QAbstractItemModel` and `QModelIndex` were already `QtCore` in Qt4 —
`uiutils.CustomModel` needed no change.

### `QFileDialog.getOpenFileName` / `getSaveFileName` tuple return

PyQt5 returns `(path, selected_filter)`. Upstream wrote a Qt4-shaped
call and post-processed with `if use_pyqt5: res = res[0]`. Replaced with
direct unpack:

| File | Old | New |
| --- | --- | --- |
| `uiutils.py::select_file`, `open_file` | `res = QFileDialog.getX(...)` then conditional `res = res[0]` | `path, _ = QtWidgets.QFileDialog.getX(...)` |

`getExistingDirectory` still returns just a string in PyQt5 — left
alone.

### Patterns flagged by the plan that did not appear

- **Old-style `QtCore.SIGNAL` / `QtCore.SLOT`**: zero hits across both
  packages (verified by `grep -rEn "QtCore\\.SIGNAL|QtCore\\.SLOT"
  packages/`). Upstream had already converted to new-style
  `widget.signal.connect(slot)` syntax during the original PyQt5
  migration attempt. Nothing to do.
- **`QString` / `UnicodeUTF8`**: zero hits.
- **`figureoptions.figure_edit` API drift**: the call in
  `plotutils_ui.py::SaveFigure.on_explore_clicked` still matches
  matplotlib's current `figure_edit(axes, parent)` signature — no patch
  needed at this phase.
- **`waitingspinnerwidget.py`**: the public-domain copy already used
  `from PyQt5.QtCore/QtWidgets/QtGui import *`; just dropped the PyQt4
  fallback branch. Imports cleanly under PyQt5 5.15. (Smoke-time
  hazards remain in the body — `setInterval(float)` and `move(float,
  float)` from Python 3 division — but those fire only at widget
  instantiation, not import; deferring to Phase 6.)

### Pre-existing bug noted but not fixed

`uiutils.py:51` defines `erro_msg` (typo), but
`PolyRegionEditor.py:151,166` calls `uiutils.error_msg`. This raises
`AttributeError` only when the user clicks Load/Save with a bad path —
it doesn't fire at import time, so Phase 5's verify is unaffected.
Leaving for Phase 6 / smoke-test triage so the rename stays in scope
with whatever else surfaces under interactive use.

## Phase 6 — CLI module, smoke tests, upstream pytest triage

`pytest packages/libwise/tests packages/wise/tests` ends at **51 passed,
8 skipped, 0 failed**. `wise --help` enumerates all 12 actions. `python
-c "import libwise, wise; print(libwise.get_version(), wise.get_version())"`
prints `0.4.7 0.4.7 (libwise: 0.4.7)`.

### CLI module

`packages/wise/src/wise/cli.py` was added per the plan template. The
entry point declared in `packages/wise/pyproject.toml`
(`wise = "wise.cli:main"`) was already wired by the editable install,
so no reinstall was needed — `wise --help` started working immediately.

`packages/wise/src/wise/actions/__init__.py` already imported each
`wise_*` submodule, so `dir(actions)` discovery worked out of the box.

### test_import.py

`packages/wise/tests/test_import.py` added per the plan template. Tests
that `import wise` succeeds and `wise.__version__` is non-empty.

### Phase 5 follow-ups

| File | Change | Why |
| --- | --- | --- |
| `libwise/waitingspinnerwidget.py` (~L85, L186, L190) | Cast `setInterval`, `move`, and `QRect` arguments to `int` | PyQt5's C++ bindings reject floats from Py3 true division; PyQt4 was lenient. Fired at widget instantiation, not import. |
| `libwise/uiutils.py:51` | Renamed `erro_msg` → `error_msg` (typo fix); also updated the commented `test_qt` example | `PolyRegionEditor.py:139,154` calls `uiutils.error_msg`. The receiving end was correct; the def was the typo. |

### Upstream pytest triage

40 failures in the initial run (after adding `pywavelets` to
`environment.yml` so `test_wtutils.py` could collect). Triage by category:

#### Fixed — numpy 2.x list-of-slices indexing

numpy 2.0 dropped the deprecation grace period and now rejects `array[list_of_slices]`. The plan flagged this generically; in practice it
hit a dozen call sites that built `index = [slice(...)] * ndim` and
indexed with the bare list. Standard fix: `array[tuple(index)]`. Fixed
in:

| File | Function / Line | Note |
| --- | --- | --- |
| `libwise/nputils.py` | `expend_slice`, `downsample`, `upsample`, `atrou`, `fill_extension`, `local_max`, `crop_threshold`, `_convolve_1d`, `_corr_convolve_fast`, `local_sum`, `zoom`, `resize`, `shift2d`, `fill_at` | Standard `tuple(index)` substitution; in `expend_slice` the function itself now returns a tuple so all callers are clean. |
| `libwise/imgutils.py` | `ImageRegion.__init__`, `ImageRegion.get_slice`, `ImageRegion.get_region_slice`, `compare_image_regions` (~L1924) | All wrap `nputils.index2slice(...)` in `tuple(...)`. |
| `wise/wds.py` | `Segment.get_cropped_segment_image`, `Segment.get_interface` | Same wrap. |

#### Fixed — Py3 true-division leftovers

2to3 doesn't convert `/` → `//` even when the operand is used as a
slice or shape. Hit a handful of sites. All were like-for-like Py2
integer-division semantics that the plan didn't enumerate (Phase 4
covered numpy aliases but not raw `/` semantics).

| File | Site | Change |
| --- | --- | --- |
| `libwise/nputils.py` | `_convolve_1d` (`l = (len(v) - 1) / 2`), `local_sum` (`l = (shape[dim] - 1) / 2`), `_corr_convolve_fast` (`l = (y.shape[dim] - 1) / 2`), `zoom` (`l = (shape[dim]) / 2`), `index2slice` (`i = len(index) / 2`) | `/` → `//` |
| `libwise/imgutils.py` | `gaussian_cylinder` (`hsx = sizex / 2`), `ellipsoide` (`hs = size / 2`), `get_ensemble_index`/`zip_index` (`len(indexs) / 2`) | `/` → `//` |
| `libwise/imgutils.py` | `gaussian` (`sigmax, sigmay = size / nsigma / 2.`) | Switched to `(size // nsigma) / 2.` to preserve the original Py2 integer-then-float semantics. With `size=5, nsigma=2`, Py2 yielded `sigma=1.0`; bare Py3 division gave `1.25`, which broke `test_gaussien_nsigma` against the upstream expected output. |
| `libwise/nputils.py` | `align_on_com` — `delta = com2[0] - com1[0]` is float; `np.zeros(shape)` then rejected float shape entries | `delta = int(round(...))` |

#### Fixed — missing stdlib import

`libwise/imgutils.py::Mask.from_mask_list` calls `reduce(...)`. Py3
moved `reduce` to `functools`. 2to3 normally adds the import, but
this one slipped through (likely because `reduce` is also used in
comprehension-only contexts that 2to3 tries to rewrite differently).
Added `from functools import reduce`.

#### Fixed — k_subset filter call

`nputils.k_subset` had `if filter is None or list(filter(arg)):` —
the `list(...)` came from a Py2 era when `filter()` returned a list.
The test passes a callable that returns `bool`, so `list(bool)` raises
`TypeError`. Stripped the `list(...)`; the truthiness of the predicate
is what was always intended.

#### Test-only fixes

| Test | Change | Why |
| --- | --- | --- |
| `test_nputils.py::test_zoom_correlation` | `sx / 2` → `sx // 2`, `corr.shape[0] / 2` → `corr.shape[0] // 2` | Test code uses `/` as an array index. |
| `test_nputils.py::test_crop_threshold` | `l[nputils.index2slice(...)]` → `l[tuple(nputils.index2slice(...))]` (×2) | Same numpy 2.x list-indexing rule. |
| `test_nputils.py::test_all_k_subset`, `test_lists_combinations` | Compare results as `set` instead of `tuple` | `nputils.uniq_subsets` returns a `set`; iteration order depends on the Python hash seed (PYTHONHASHSEED randomization). The Py2-era tests asserted a specific ordering — that was always implementation-defined. |
| `test_imgutils.py::test_image_region_zoom` | `np.array(...) / 2 + shift` → `// 2`; force `int(zcx), int(zcy)` | Indexing fix. (Then test was skipped — see below.) |
| `test_imgutils.py::test_region_image` | `[100 - 5 / 2, 65]` → `[99 - (5 - 1) // 2, 65]` plus a comment explaining the geometry | The original expectation was wrong even in Py2: with `seg3.shape=(5, 11)` clipped against the right image edge, the visible center sits at `99 - (5-1)//2 = 97`, not `100 - 5/2 = 98`. Test expectation was off-by-one — the implementation has been correct all along. |

#### Skipped — testing functions that don't exist in upstream

| Test | Reason |
| --- | --- |
| `test_nputils.py::test_get_points_around` | `nputils.get_points_around` is not implemented in upstream — never existed. |
| `test_nputils.py::test_per_ext`, `test_symm_ext` | `nputils.per_extension` and `symm_extension` are commented out in upstream `nputils.py` (~L1295, L1321) and never reinstated. The tests were testing dead code. |
| `test_nputils.py::test_norm_xcorr` | Body ends with bare `assert False` — incomplete debug stub the upstream author left. |
| `test_imgutils.py::test_join_image_region` | Body ends with `assert False` — incomplete debug stub. |
| `test_imgutils.py::test_stack_image` | Constructs `imgutils.StackedImage(a.data)` from a bare ndarray, but `StackedImage.__init__` calls `fits_image.get_epoch()`. The constructor expects a `FitsImage`. Body also ends with `assert False`. |
| `test_imgutils.py::test_image_region_zoom` | `ImageRegion.zoom(center, shape)` does not exist — only the inherited `Image.zoom(factor)` does. Test was written against a method that was never implemented. |
| `test_imgutils.py::test_mask` | Constructs `imgutils.Region([5, 5])` then calls `.add_rectangle(...)`. `Region` is a `pyregion.open(filename)` wrapper — there is no shape-constructor and no `add_rectangle`/`get_mask` on it. Test was written against a different (mythical) `Region` class. |

`test_nputils.py::test_convolve` was kept (and passes) but the
`symm_extension` and `per_extension` reference assertions inside it
were removed for the same reason as the skipped extension tests.

#### Environment additions

`pywavelets>=1.4` was added to `environment.yml`. `test_wtutils.py`
uses `pywt` as a reference implementation to cross-check libwise's
own (from-scratch) wavelet transforms; without it the test module
won't even collect. Production libwise code does not import `pywt`.

## Phase 8 — first-user smoke test (3C120 walkthrough)

Ran the full pipeline on 10 epochs of `0430+052.u.2012_*.icn.fits`
(`wise info` → `settings set` → `stack` → `detect` → `match`). The
upstream pytest sweep in Phase 6 didn't exercise these end-to-end CLI
paths, so each new step surfaced a Py2→Py3 regression that 2to3 missed
or that needed manual cleanup. All seven were minimal mechanical fixes
of the same family already documented in Phase 6 — none touched
algorithm or I/O semantics.

### Fixed — `list(filter(...))` over a local-variable callable

`imgutils.fast_sorted_fits` (line 257) had `if not list(filter(date)):`
where `filter` is a local variable holding a `bool`-returning
predicate built by `nputils.date_filter`. 2to3 wrapped the call in
`list(...)` because it assumed `filter` was the Python 3 lazy
builtin. Same pattern Phase 6 fixed in `nputils.k_subset` ("verify
grep wasn't strict enough" — true again). Stripped the `list(...)`.

| File | Old | New |
| --- | --- | --- |
| `libwise/imgutils.py:257` | `if not list(filter(date)):` | `if not filter(date):` |

### Fixed — configparser binary-mode write

`nputils.ConfigurationsContainer.to_file` opened the config file with
`'wb'`, but `configparser.RawConfigParser.write()` requires text mode
in Py3 (Py2 wrote bytes). Switched to `'w'` — the writer's `[section]`
header `format(...)` call was the actual `TypeError` source.

| File | Old | New |
| --- | --- | --- |
| `libwise/nputils.py:2219` | `with open(filename, 'wb') as fh:` | `with open(filename, 'w') as fh:` |

### Fixed — `print(list(string))` in `wise settings show`

`wise/actions/wise_settings.py` had `print(list(config.values()))`
and `print(list(section.values()))`. `Configuration.values()` returns
a fully formatted multi-line string; the `list(...)` wrap iterated it
into a list of single characters, so `wise settings show data`
printed `['D', 'a', 't', 'a', ...]`. The wrap was a 2to3 leftover
(Py2 `print list(...)` → Py3 `print(list(...))`); the underlying
`list(string)` was already wrong but harmless under Py2 print
formatting. Dropped the `list(...)`.

| File | Old | New |
| --- | --- | --- |
| `wise/actions/wise_settings.py:85, 93` | `print(list(config.values()))`, `print(list(section.values()))` | `print(config.values())`, `print(section.values())` |

### Fixed — Py3 dropped `cmp=` on `sorted()` and the `cmp()` builtin

The matching/segmentation code used 3-way comparators throughout
(`sorted_list(cmp=cmp_intensity)` plus `cmp_intensity = lambda x, y: cmp(...)`).
`sorted()` in Py3 only accepts `key=`, and `cmp()` itself was removed
from builtins. Two-part fix:

1. `features.FeaturesGroup.sorted_list` now wraps the cmp argument
   with `functools.cmp_to_key` when given. Existing `sorted_list(cmp=...)`
   call sites (matcher, wds, wiseutils, tasks) keep working unchanged
   on the call side. Also rewrote the two `sorted(founds, cmp=...)`
   sites in `find` / `find_at_coord` to plain `key=lambda x: x[1]`
   (they were sorting by a scalar distance — no cmp needed).
2. Added a private `_cmp(a, b)` helper in `features.py` and imported
   it explicitly into `wds.py`, `matcher.py`, `wiseutils.py`, and
   `tasks.py` (it starts with `_`, so `from .features import *` does
   not re-export it). All `cmp(...)` call sites switched to `_cmp(...)`.
   First impl `(a > b) - (a < b)` raised on numpy bools — replaced
   with `if/elif` form that returns `-1 / 1 / 0` and accepts numpy
   scalars.

| File | Change |
| --- | --- |
| `wise/features.py` | Added `from functools import cmp_to_key`; added module-level `_cmp(a, b)`; rewrote `find`/`find_at_coord` to `key=lambda x: x[1]`; `sorted_list` now does `sorted(l, key=cmp_to_key(cmp))` when `cmp is not None`; `Feature.__cmp__` body switched to `_cmp` (still dead in Py3 — see below) |
| `wise/wds.py` | `from .features import _cmp`; `cmp_intensity = lambda x, y: _cmp(...)` |
| `wise/matcher.py` | Same import + 2 lambda rewrites |
| `wise/wiseutils.py` | Same import + 5 lambda rewrites |
| `wise/tasks.py` | Same import + 1 lambda rewrite |

`grep -rn ' cmp(' packages/ --include='*.py'` is now clean of the
Py2 builtin.

### Fixed — `Feature` had no `__lt__` for Py3 sort

Py2 `Segment.sort()` (Segment subclasses Feature) drove ordering
through `Feature.__cmp__`. Py3 `list.sort()` ignores `__cmp__` and
calls `__lt__`. `nputils.uniq_subsets` does `y.sort()` on a list of
Segments and raised `TypeError: '<' not supported between instances
of 'Segment' and 'Segment'`. Added `__lt__` that delegates to the
existing `__cmp__`:

| File | Added |
| --- | --- |
| `wise/features.py::Feature` | `def __lt__(self, other): return self.__cmp__(other) < 0` |

`__cmp__` itself stays — it is called explicitly by nothing in Py3,
but it still encodes the intended tie-break order (initial_coord[0]
→ initial_coord[1] → intensity), and `__lt__` reuses it.

### Fixed — float shift produces float slice indices

`imgutils.ImageRegion.set_shift` stored `self.shift = np.round(shift)`,
which returns a `float64` array. Downstream `get_region_slice()` then
built `slice(-(x0 + dx), None)` etc. — Py3 strictly requires int
slice indices (Py2 was lenient under some numpy versions). Cast the
rounded result:

| File | Old | New |
| --- | --- | --- |
| `libwise/imgutils.py::ImageRegion.set_shift` (~L1706) | `self.shift = np.round(shift)` | `self.shift = np.round(shift).astype(int)` |

### Fixed — FITS files opened in text mode

`imgutils.is_fits` and `imgutils.FastHeaderReader.read` opened the
file with `open(file)` — Py3 default is text mode with the platform
locale codec. The 3C120 walkthrough did not surface this because real
.icn.fits headers span multiple 2880-byte blocks of pure ASCII, so
the text-mode buffered decoder happened to succeed on the first
chunk. The new pytest-driven synthetic FITS (single-block header,
binary data starting at byte 2880) hits the binary region inside the
buffered read and raises `UnicodeDecodeError`. Switched both to
binary mode; in `FastHeaderReader.read`, decode each 80-byte line as
ASCII (FITS spec), with `errors='replace'` so a malformed line
degrades gracefully into a non-matching string instead of crashing
mid-iteration.

| File | Old | New |
| --- | --- | --- |
| `libwise/imgutils.py::is_fits` | `with open(file) as f: return f.read(6) == 'SIMPLE'` | `with open(file, 'rb') as f: return f.read(6) == b'SIMPLE'` |
| `libwise/imgutils.py::FastHeaderReader.read` | `with open(self.file) as fd: ... line = fd.read(80)` | `with open(self.file, 'rb') as fd: ... line = fd.read(80).decode('ascii', errors='replace')` |

### Locked in via pytest

The seven Phase 8 fixes are now exercised by
`packages/wise/tests/test_smoke_pipeline.py`. The test generates a
2-epoch 64×64 synthetic FITS dataset (two gaussians per epoch, one
shifted slightly between epochs), drives `AnalysisContext.detection()`
and `AnalysisContext.match()` directly (bypassing the interactive
CLI prompts in `wise detect`), and asserts that the orchestration
layer completes without traceback. SNR thresholds are bumped
(`alpha_threashold=10`, `alpha_detection=15`) and the noise floor
is kept at σ=0.001 so the matcher's `optimize()` step stays
combinatorially bounded — the test exists to catch port regressions,
not to characterize matcher convergence on noisy synthetic input.

### Verification

`stack`, `detect` (10 epochs), and `match` (9 epoch pairs × 4 scales)
now run to completion against the 3C120 dataset. Artifacts written
to `result/`: `result.ms.dat` (477 lines, all-features list),
`result.set.dat` (10 lines, one per FITS file), and four
`result_{4,6,8,12}.ms.dfc.dat` matched-component lists (114, 94, 83,
67 lines respectively). Match-ratio summary printed at the end was
`Sum:27, Mean:0.751, P90:1` — i.e. 27 of 36 scale×epoch matches at
≥correlation_threshold 0.65, in line with the upstream walkthrough's
expected order. No warnings from this run other than two
`Warning: high total features to optimize` notices on the
2012-11-02→2012-11-28 pair, which are upstream-emitted hints from
`matcher.optimize`, not port-related.

GUI viewers (`wise view`, `view_features`, `plot_features`,
`plot_sep_from_core`, `view_links`) were out of scope for this smoke
run and have not yet been exercised — Phase 5 verified Qt imports
clean but not interactive widget behavior under PyQt5. See Phase 8b
below for `view_features`.

## Phase 8b — GUI smoke test (`wise view_features`)

First exercise of a GUI viewer under PyQt5 against the Phase 8 result
artifacts (`wise view_features result 8`). Surfaced a pandas-2.0
removal: `DataFrame.append`, removed in pandas 2.0, was crashing
`SSPData.add_features_group` before the Qt window could open.

### Fixed — `DataFrame.append` removed in pandas 2.0

| File | Old | New |
| --- | --- | --- |
| `wise/wiseutils.py::SSPData.add_features_group` (~L843) | `self.df = self.df.append(df)` | `self.df = pd.concat([self.df, df], ignore_index=True)` |

Used `ignore_index=True`: the SSPData `view_*` code paths consume the
frame via `data.df['features'].values`, `data.df.groupby('region')`,
and column-aligned `pd.Series(..., index=self.df.index)` assignment —
none of which depend on the original `feature.get_id()` values being
preserved as the row index.

### Other pandas-deprecation patterns audited (clean)

| Pattern | Found? |
| --- | --- |
| `.iteritems(` | none |
| `squeeze=True` (read_csv) | none |
| `.lookup(` | none |
| `.ix[` | none |

### Fixed — `DataFrame.as_matrix()` removed in pandas 1.0

| File | Old | New |
| --- | --- | --- |
| `wise/wiseutils.py::VelocityData.add_delta_info` (~L900) | `cdf[['ra_error', 'dec_error']].as_matrix().T` | `cdf[['ra_error', 'dec_error']].to_numpy().T` |

Behavior is identical for the extraction case (2-D float numeric
columns → 2-D ndarray). Single call site in the codebase; not on the
`view_features` path so the GUI smoke didn't trip on it, but the
velocity/match-result code paths now run too.

### Silenced — `np.loadtxt` "Input line 1 contained no data" warning

numpy 1.23+ emits a `UserWarning` from `np.loadtxt` whenever the
first line is comment-only — the `wise.savetxt`-written `.ms.dat` and
`.ms.dfc.dat` files start with two-or-three `#`-prefixed header lines,
so every `from_file` load printed the warning. `np.genfromtxt` takes
a different code path that doesn't emit the warning, returns the
identical `(N, ncol)` `<U`-dtype array for `dtype=str, delimiter=' '`
input, and is a 1-token swap. Verified shape/dtype/contents bit-equal
on the 474-row `result.ms.dat` from the 3C120 walkthrough.

| File | Old | New |
| --- | --- | --- |
| `wise/wds.py::MultiScaleImageSet.from_file` (~L878) | `np.loadtxt(file, dtype=str, delimiter=' ')` | `np.genfromtxt(file, dtype=str, delimiter=' ')` |
| `wise/matcher.py::FeaturesLinkBuilder.from_file` (~L473) | same | same |

### Verification

`cd ~/wise-test && QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg \
  timeout 10 wise view_features result 8` runs through
`SSPData.from_results` → `add_features_group` and reaches the Qt
event loop with **zero** stderr output (process killed by timeout, not
by exception). `pytest packages/libwise/tests packages/wise/tests`
still 52 passed, 8 skipped.

## Phase 8c — matplotlib 3.3+ toolbar API drift (`_active` → `mode`)

`libwise.plotutils_ui.ExtendedNavigationToolbar` (a Qt5
`NavigationToolbar2QT` subclass that adds custom Profile/Stats modes)
referenced the parent's `self._active` private attribute. matplotlib
3.3 replaced it with `self.mode`, a `_Mode` enum (`NONE`/`PAN`/`ZOOM`).
Reading `self._active` on matplotlib ≥3.3 raises `AttributeError` as
soon as the user clicks Pan/Zoom (or hovers, depending on backend).

The subclass was using `_active` for two things at once:

1. detecting matplotlib's built-in PAN/ZOOM state, and
2. tracking its own custom PROFILE/STATS toggle state.

Split those: PAN/ZOOM now read from `self.mode.name`; PROFILE/STATS
keep `self._active`, but the subclass now initializes
`self._active = None` itself (the parent no longer provides it).

| File / call site | Old | New |
| --- | --- | --- |
| `plotutils_ui.py::ExtendedNavigationToolbar.__init__` | (relied on parent's `self._active`) | adds `self._active = None` after `super().__init__` |
| `…zoom` (~L674) | `if self._active != 'ZOOM':` | `if self.mode.name != 'ZOOM':` |
| `…pan` (~L679) | `if self._active != 'PAN':` | `if self.mode.name != 'PAN':` |
| `…toogle_off_all_active` (~L703) | one-arm check on `self._active in ('ZOOM','PAN','STATS','PROFILE')` | two-arm: `self.mode.name in ('ZOOM','PAN')` first, else `self._active in ('STATS','PROFILE')` |

Other PROFILE/STATS uses of `self._active` (lines 670–671, 684–705)
stayed as-is — they only ever store/compare custom-mode state.

### Other removed private toolbar internals audited (clean)

| Pattern | Found? |
| --- | --- |
| `_idPress` / `_idRelease` | none |
| `_lastCursor` | none |
| `_active` in `libwise/app/*` (e.g. PolyRegionEditor) | none |

(Note: `WaveletDenoise.py` has a `self.mode` attribute, but it's a
`hard`/`soft` denoising-mode UI control unrelated to the toolbar.)

### Verification

Direct toolbar exercise under matplotlib 3.10 / PyQt5 5.15:

```text
instantiated OK; mode.name='NONE'; _active=None
after zoom():        mode.name='ZOOM', _active=None
after zoom() again:  mode.name='NONE', _active=None
after pan():         mode.name='PAN',  _active=None
after toogle_off:    mode.name='NONE', _active=None
```

`pytest packages/libwise/tests packages/wise/tests` still 52 passed,
8 skipped. `cd ~/wise-test && QT_QPA_PLATFORM=offscreen MPLBACKEND=Agg
timeout 10 wise view_features result 8` reaches the Qt event loop
with zero stderr.
