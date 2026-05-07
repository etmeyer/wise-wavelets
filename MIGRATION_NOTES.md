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
