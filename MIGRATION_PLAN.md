# WISE / libwise — Python 3 modernization plan

A gameplan for porting [flomertens/wise](https://github.com/flomertens/wise)
and its companion library [flomertens/libwise](https://github.com/flomertens/libwise)
from Python 2 to a current scientific-Python stack. Both packages were last
released against Python 2; `wise` depends heavily on `libwise`, so they must
be ported together.

This document is the brief for the executor (Claude Code or a human). The
working directory `wise_mertens/` is currently empty; everything is built up
from scratch.

---

## Decisions (already made — don't relitigate unless something blocks)

| Decision | Choice |
| --- | --- |
| Target Python | **3.11+** |
| Repository shape | **Monorepo** with two packages under `packages/libwise/` and `packages/wise/` |
| Layout | **src layout** for both packages (`src/libwise/...`, `src/wise/...`) |
| libwise treatment | **Fork & modernize in lockstep** (not vendor, not replace) |
| Scope | **Everything, including the PyQt UI** (`libwise/app/`, `plotutils_ui.py`) |
| Environment | **conda** via `environment.yml` at the repo root, conda-forge channel; the two in-tree packages installed editable with `pip install -e` |
| Build backend | **hatchling** for each package's wheel (declared in per-package `pyproject.toml`) |
| Qt binding | **PyQt5** (upstream README says Qt5 but imports are mixed Qt4/Qt5; standardize on PyQt5) |
| Lint/format | **ruff** (lenient initially), **pytest** for the existing test suite |
| Package names on PyPI | `libwise` and `wisetool` (same names as upstream — bump version to `0.5.0.dev0` to denote the fork) |

---

## Repository layout (target)

```
wise_mertens/
├── .gitignore
├── README.md
├── MIGRATION_NOTES.md           # log of substitutions made (filled in as you go)
├── environment.yml              # conda env definition (source of truth for dev deps)
├── pyproject.toml               # tool-only (ruff, pytest); no [project] table
├── packages/
│   ├── libwise/
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   ├── LICENSE              # GPL-2.0 from upstream
│   │   ├── src/libwise/         # all Python sources
│   │   │   ├── __init__.py
│   │   │   ├── app/             # PyQt UI submodule
│   │   │   ├── presets/         # *.preset data files
│   │   │   └── resources/       # icons (renamed from upstream's misspelled "ressource/")
│   │   ├── tests/               # from upstream test/
│   │   └── scripts/             # fits-crop, wt-denoise, wt2d
│   └── wise/
│       ├── pyproject.toml
│       ├── README.md
│       ├── LICENSE
│       ├── src/wise/
│       │   ├── __init__.py
│       │   ├── actions/         # CLI subcommands
│       │   ├── contrib/         # auxiliary user scripts
│       │   └── cli.py           # NEW — entrypoint replacement for scripts/wise
│       ├── tests/               # NEW (none upstream); add at minimum import tests
│       └── scripts/             # legacy `wise` script (kept for parity, not the install entrypoint)
```

Use `[project.scripts]` in `packages/wise/pyproject.toml` to install `wise` as
`wise.cli:main` rather than relying on the legacy shebang script.

---

## Phases

Each phase ends in a state that can be committed and verified. **Commit between
phases.** This makes the diff auditable and gives you bisection points if
something breaks later.

### Phase 0 — Scaffold

1. `git init -b main` in `wise_mertens/`.
2. Create `environment.yml` per the template at the bottom of this doc.
3. Create a tool-only root `pyproject.toml` (no `[project]` table — this file
   exists only to hold `[tool.ruff]` and `[tool.pytest.ini_options]` so both
   packages share lint/test config). See template at the bottom.
4. Create `.gitignore` (Python + conda + IDE).
5. Create `packages/libwise/pyproject.toml` and `packages/wise/pyproject.toml`
   per the templates at the bottom of this doc.
6. Create top-level `README.md` and an empty `MIGRATION_NOTES.md` to be filled
   as you go.

**Verify:** `conda env create -f environment.yml --dry-run` parses and
resolves without error. (The `pip install -e` lines inside `environment.yml`
will fail at this point because the packages don't have source yet — that's
expected; they succeed after Phase 1.)

**Commit:** `chore: scaffold conda environment + per-package pyproject for libwise and wise`

### Phase 1 — Import upstream verbatim, then run `2to3`

The intent is two commits per package — one with raw upstream code, one with
the 2to3 output — so the mechanical-vs-manual changes are separable in the diff.

1. `git clone https://github.com/flomertens/libwise /tmp/libwise_upstream`
2. Copy `libwise/libwise/*` → `packages/libwise/src/libwise/`, `libwise/test/*` →
   `packages/libwise/tests/`, `libwise/scripts/*` → `packages/libwise/scripts/`,
   `libwise/LICENSE` → `packages/libwise/LICENSE`.
3. Same for `flomertens/wise` into `packages/wise/`.
4. **Commit:** `chore: import upstream libwise + wise sources verbatim (Python 2)`
5. Run `2to3` on every `.py` and on the scripts:
   ```
   python3 -m lib2to3 -w -n --no-diffs \
     packages/libwise/src/libwise \
     packages/libwise/tests \
     packages/libwise/scripts \
     packages/wise/src/wise \
     packages/wise/scripts
   ```
   (Use `python3 -c "from lib2to3.main import main; main('lib2to3.fixes')"` if
   `2to3` isn't on PATH.)
6. **Commit:** `refactor: 2to3 over libwise + wise (mechanical only)`

**Verify:** `grep -rn "print [^(]" packages/` returns nothing (other than
docstrings/comments). `grep -rn "from types import NoneType" packages/`
returns ~4 hits in `packages/wise/src/wise/scc.py` — kept until phase 2.
2to3 also auto-converts `import ConfigParser` → `import configparser`
(observed in `libwise/nputils.py`); phase 2 audits the call sites.

### Phase 2 — Fix imports: implicit-relative, removed stdlib, moved scipy

2to3 catches `print`, `except X, e:`, `dict.iteritems()`, etc. but does **not**
fix implicit relative imports inside packages, removed-stdlib modules, or
moved scipy submodules. Do those now.

#### 2a. Implicit relative imports

Upstream uses Py2 implicit relative imports inside both packages. 2to3 *should*
catch most of these (`-f import` fixer), but verify:

- `wise/__init__.py`: `from features import *` etc. → `from .features import *`
- `libwise/__init__.py` / `app/*.py`: same pattern with `plotutils_base`, etc.

Inside `wise/actions/*.py` you'll see `import wise` (the actions module
importing its parent package). That's an absolute import and works under Py3
as long as the package is installed — leave it alone.

#### 2b. Removed stdlib

| Old | New |
| --- | --- |
| `import ConfigParser` | 2to3 already rewrites the import to `import configparser`. Audit the call sites and update any that still reference the `ConfigParser.` prefix to `configparser.` (alias if too noisy). |
| `from types import NoneType` | delete; replace usage with `type(None)`. (Observed: ~4 sites in `wise/scc.py` after Phase 1.) |
| `import imghdr` | removed in 3.13 — replace with `from PIL import Image` and detect via `Image.open(path).format` |
| `from cStringIO import StringIO` | `from io import BytesIO` (binary) or `StringIO` (text) — pick by call-site |

#### 2c. Moved scipy / numpy submodules

Submodules are deprecated since SciPy 1.10 and *gone* in newer releases:

| Old | New |
| --- | --- |
| `from scipy.ndimage.filters import convolve1d` | `from scipy.ndimage import convolve1d` |
| `from scipy.ndimage.interpolation import rotate, zoom, map_coordinates` | `from scipy.ndimage import rotate, zoom, map_coordinates` |
| `from scipy.ndimage.measurements import center_of_mass, label` | `from scipy.ndimage import center_of_mass, label` |
| `from scipy.ndimage.morphology import grey_dilation` | `from scipy.ndimage import grey_dilation` |
| `from scipy.ndimage import measurements` (then `measurements.label`) | `from scipy import ndimage as ndi` then `ndi.label` |
| `from scipy import misc` (image read/save/imresize) | `imageio.v3` for I/O; `skimage.transform.resize` for resize. Pick the right one per call site. |
| `from scipy import misc` (sample image, e.g. `misc.face()`) | `skimage.data.chelsea()` (or another `skimage.data.*`). Plan didn't anticipate sample-image use. Encountered in `libwise/imgutils.py::lena()`. |
| `from scipy.ndimage import measurements` (then `measurements.center_of_mass`) | Either `from scipy.ndimage import center_of_mass` and call directly, or alias the module. Encountered alongside `center_of_mass` in `libwise/imgutils.py`; consolidated into the direct import. |
| `from scipy.misc import lena` (Py2-era sample image, removed long ago) | The function is dead in `libwise/nputils.py::test_upsample` (imported but never referenced) — drop the import. |

Quick scan command after edits:
```
grep -rEn "scipy\.ndimage\.(filters|interpolation|measurements|morphology)|scipy\.misc|from types import NoneType|import ConfigParser|import imghdr" packages/
```
Should return nothing.

**Commit:** `refactor: fix relative imports and removed/moved stdlib+scipy modules`

### Phase 3 — Replace pymorph with scikit-image

`pymorph` is abandoned and Py2-only. Find every call site and replace with
the scikit-image equivalent. Mapping:

| pymorph call | scikit-image equivalent |
| --- | --- |
| `pymorph.dilate(img, se)` | `skimage.morphology.dilation(img, se)` |
| `pymorph.erode(img, se)` | `skimage.morphology.erosion(img, se)` |
| `pymorph.open(img, se)` | `skimage.morphology.opening(img, se)` |
| `pymorph.close(img, se)` | `skimage.morphology.closing(img, se)` |
| `pymorph.label(img)` | `skimage.measure.label(img)` |
| `pymorph.regmin(img)` / `regmax` | `skimage.morphology.local_minima(img)` / `local_maxima` |
| `pymorph.gradm(img)` | `skimage.filters.rank.gradient(img, footprint)` (footprint required) |
| `pymorph.thin(img)` | `skimage.morphology.thin(img)` |
| `pymorph.sebox(r)` / `pymorph.sedisk(r)` | `skimage.morphology.square(2*r+1)` / `disk(r)` |
| `pymorph.secross(r)` | `skimage.morphology.diamond(r)` (L1-ball footprint; not in original table — added during Phase 3) |

Pay attention to **return type and shape**:
- `pymorph.label` returned `(labels, nlabels)` from some entry points and just
  `labels` from others — `skimage.measure.label` returns just `labels` unless
  `return_num=True`. Audit each call site.
- `pymorph` operated on uint8 binary arrays implicitly; `skimage` is mostly
  bool/float. Cast as needed.

The modern per-package `pyproject.toml` files don't list `pymorph` (we
never added it), and `environment.yml` doesn't either — so there's nothing
to remove from install metadata. Just delete every `import pymorph`
statement and replace the call sites. The audit trail for each
substitution lives in `MIGRATION_NOTES.md` (file, pymorph call, skimage
replacement, judgment-call rationale) rather than as inline `# was
pymorph.X` comments — that keeps the verify grep at zero.

**Reality from Phase 3 execution:** the upstream code only ever called
`pymorph.secross` (one site, in `libwise/nputils.py`). None of `dilate`,
`erode`, `open`, `close`, `label`, `regmin`, `regmax`, `gradm`, `thin`,
`sebox`, or `sedisk` appeared, so the label-unpacking and gradm-footprint
hazards above never materialized. The README dependency lists for both
packages also mentioned `pymorph`; those lines were dropped here so the
verify grep is clean. (Phase 7 rewrites the READMEs in full.)

**Verify:** `grep -rn "pymorph" packages/` returns zero. Existing tests in
`packages/libwise/tests/test_imgutils.py` should still pass for any image-op
tests (or fail with informative output identifying what behavior shifted).

**Commit:** `refactor: replace pymorph with scikit-image equivalents`

### Phase 4 — Update numpy 2.x / skimage / astropy / matplotlib drift

#### numpy 2.x

The conda solve pulls numpy ≥ 2.0 (2.4 observed). Several aliases the
upstream code likely uses were removed in numpy 2.0. Audit and replace:

| Old | New |
| --- | --- |
| `np.float_` | `np.float64` |
| `np.complex_` | `np.complex128` |
| `np.int_` | `np.intp` (or `int`, by use) |
| `np.unicode_` | `np.str_` |
| `np.row_stack` | `np.vstack` |
| `np.cast[dtype](x)` | `np.asarray(x, dtype=dtype)` or `x.astype(dtype)` |
| `np.product` | `np.prod` |
| `np.alltrue` / `np.sometrue` | `np.all` / `np.any` |
| `np.in1d` | `np.isin` |
| `np.PINF` / `np.NINF` / `np.NAN` | `np.inf` / `-np.inf` / `np.nan` |
| `np.compat.*` | gone — most callers want plain Python equivalents |
| Implicit `__array__()` no-arg | now requires `dtype` and `copy` kwargs in numpy 2.x |

`numpy.testing` still exists. `np.bool8` and `np.object0` are gone — use
`bool` / `object`. If `nputils.py` defines its own dtype helpers, expect
hits there.

#### scikit-image

| Old | New |
| --- | --- |
| `from skimage.morphology import watershed` | `from skimage.segmentation import watershed` (moved in 0.19) |
| `skimage.measure.regionprops` returning attributes via dict-like access | use the `RegionProperties` attributes directly (`r.area`, `r.bbox`) |
| `selem=` keyword in morphology | renamed to `footprint=` in 0.19 |

#### astropy

- `astropy.io.fits as pyfits` is fine.
- `astropy.units` and `astropy.wcs` API is stable, but watch for
  `astropy.units.quantity_input` decorator changes if used.
- `astropy.cosmology` is stable but cosmology objects are now immutable; if
  upstream sets attributes after construction, that needs to change.
- `astropy.time.TimeDelta` works the same; check for `format='gps'` which
  no longer accepts plain ints in some versions.

#### matplotlib

- `from mpl_toolkits.axisartist.grid_finder import MaxNLocator` still works.
- `from matplotlib.mlab import dist_point_to_segment` was removed — copy the
  function inline (it's ~5 lines) or use `shapely.geometry.LineString`.
- `matplotlib.backends.backend_qt4agg` → `backend_qt5agg`
- `matplotlib.backends.qt_editor.figureoptions` is still importable but its
  API has shifted; if upstream patches it, expect breakage.

#### pyregion

`pyregion` is alive but the API drifted. The module is now mostly a thin
wrapper over `regions` (the modern replacement). For robust forward
compatibility, consider using `regions` directly. For minimum-change, keep
`pyregion` and patch any `ShapeList` API changes on a case-by-case basis.

**Verify:** `python -c "import libwise; import wise"` succeeds with **no**
ImportError.

**Commit:** `refactor: skimage/astropy/matplotlib API drift`

### Phase 5 — Modernize Qt UI

Most of `libwise/plotutils_ui.py` and everything in `libwise/app/` is
Qt-based. Upstream is mixed — some files use PyQt4 import paths, some Qt5.
Standardize on **PyQt5** (declared as the `[ui]` extra of `libwise`).

1. Replace `PyQt4.QtCore` / `PyQt4.QtGui` imports with `PyQt5.QtCore` /
   `PyQt5.QtWidgets` (most widgets moved from `QtGui` to `QtWidgets`).
2. `from matplotlib.backends.backend_qt4agg import ...` →
   `from matplotlib.backends.backend_qt5agg import ...`.
3. `QtCore.SIGNAL` / `QtCore.SLOT` old-style signals → new-style:
   `widget.someSignal.connect(handler)`.
4. `QApplication.UnicodeUTF8` and `QString` are gone — strings are just `str`.
5. `QFileDialog.getOpenFileName` now returns `(filename, filter_used)` tuple,
   not just filename.
6. The `waitingspinnerwidget.py` has a public-domain origin — verify the
   bundled copy still works against PyQt5 and patch if not.

**Verify:** `python -c "from libwise.app import PolyRegionEditor"` imports
cleanly. Smoke-test by launching the wt-denoise script on a sample FITS file
(headlessly: `MPLBACKEND=Agg`).

**Commit:** `refactor: port Qt UI to PyQt5`

### Phase 6 — Smoke tests + existing tests

1. `conda env create -f environment.yml` from repo root, then `conda activate
   wise`. The `pip:` block inside `environment.yml` installs both in-tree
   packages editable. (If the env already exists, `conda env update -f
   environment.yml --prune` instead.)
2. `python -c "import libwise, wise; print(libwise.get_version(), wise.get_version())"`.
3. `pytest packages/libwise/tests`. The upstream test files
   (`test_nputils.py`, `test_imgutils.py`, `test_wtutils.py`) target the Py2
   API in places — expect some failures, fix them as you find them, document
   in `MIGRATION_NOTES.md`.
4. Add a tiny `packages/wise/tests/test_import.py`:
   ```python
   def test_import():
       import wise
       assert wise.__version__
   ```
5. Smoke-test the CLI: `wise --help` (after creating `wise/cli.py` — see
   "CLI replacement" below).

**Commit:** `test: smoke tests for both packages`

### Phase 7 — Polish

- Fill in `MIGRATION_NOTES.md` with the running log of every non-mechanical
  substitution. (Phase 3's pymorph table is the example; add similar tables
  for skimage/astropy/Qt as you encounter call sites.)
- Update `README.md` install instructions: `conda env create -f
  environment.yml && conda activate wise` for dev; once published, users get
  `conda install -c conda-forge libwise wisetool` (or `pip install libwise
  wisetool` if PyPI-only).
- Optionally generate a per-platform lockfile with `conda-lock lock -f
  environment.yml` and commit `conda-lock.yml` for reproducible installs.
- Run `ruff check` and fix or `# noqa` the genuine warnings; the science
  code uses single-letter names heavily (`l`, `I`) — keep `E741` ignored.
- Add a CHANGELOG entry / GitHub release notes draft.

**Commit:** `docs: migration notes, README, ruff config`

---

## CLI replacement

Upstream's `scripts/wise` discovers actions via `dir(wise.actions)`. Re-implement
as `packages/wise/src/wise/cli.py`:

```python
"""Entry point for the `wise` command. Replaces upstream scripts/wise."""
from __future__ import annotations

import re
import sys

from wise import actions


def _discover_tasks() -> dict[str, object]:
    return {
        m[len("wise_") :]: getattr(actions, m)
        for m in dir(actions)
        if re.fullmatch(r"wise_[\w_]+", m)
    }


def _usage(tasks: dict[str, object]) -> str:
    pad = max(len(t) for t in tasks) + 4
    lines = [
        f"  {t:<{pad}}{getattr(mod, 'USAGE', '').splitlines()[0]}"
        for t, mod in tasks.items()
    ]
    return "Usage: wise TASK [OPTIONS]\n\nAvailable tasks:\n" + "\n".join(lines)


def main() -> int:
    tasks = _discover_tasks()
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(_usage(tasks))
        return 0 if len(sys.argv) >= 2 else 1
    name = sys.argv[1]
    if name not in tasks:
        print(f"Error: No task named {name!r}\n\n{_usage(tasks)}", file=sys.stderr)
        return 1
    sys.argv = sys.argv[1:]
    return tasks[name].main() or 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Wire it via `[project.scripts] wise = "wise.cli:main"` in
`packages/wise/pyproject.toml`. Keep the legacy `scripts/wise` shebang in the
tree for parity but don't install it via `[tool.hatch.build]`.

---

## `environment.yml` template

```yaml
name: wise
channels:
  - conda-forge
  - nodefaults
dependencies:
  - python=3.11
  - numpy>=1.24
  - scipy>=1.11
  - scikit-image>=0.22
  - astropy>=6.0
  - matplotlib>=3.7
  - pyregion>=2.2
  - uncertainties>=3.2
  - pandas>=2.0
  - pillow>=10.0
  - appdirs>=1.4
  - imageio>=2.31
  - jsonpickle>=3.0
  - pyqt>=5.15            # PyQt5 — drives libwise/app and plotutils_ui
  - pytest>=8.0
  - ruff>=0.6
  - pip
  - pip:
    - -e packages/libwise
    - -e packages/wise
```

A few notes:

- `pyqt` from conda-forge resolves to **PyQt5** at v5.15.x. If you ever need
  PyQt6, switch the line to `pyqt=6` (and update Phase 5 imports accordingly).
- The `pip:` block runs after the conda solve, installing the two in-tree
  packages editable into the conda env.
- If conda's solve is slow, set `conda config --set solver libmamba` (default
  on conda ≥ 23.10).
- For pinned, reproducible installs across platforms, run `conda-lock lock -f
  environment.yml` and commit the resulting `conda-lock.yml`.

## Root `pyproject.toml` template (tool-only)

```toml
# This file holds shared tool config only. There is no [project] table at the
# root — the two installable packages live under packages/libwise and
# packages/wise, each with its own pyproject.toml.

[tool.ruff]
line-length = 110
target-version = "py311"
extend-exclude = ["build", "dist"]

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP"]
ignore = [
    "E501",  # line length handled by formatter
    "E741",  # legacy ambiguous names (l, I) used widely in the science code
    "F401",  # re-exports via `from .x import *` are intentional in __init__
    "F403",
    "F405",
]

[tool.pytest.ini_options]
testpaths = ["packages/libwise/tests", "packages/wise/tests"]
filterwarnings = ["ignore::DeprecationWarning"]
```

## pyproject template — `packages/libwise/pyproject.toml`

```toml
[project]
name = "libwise"
version = "0.5.0.dev0"
description = "Utilities for plotting, wavelet transforms, image processing, and Qt UI (modernization fork)"
authors = [{ name = "Florent Mertens", email = "flomertens@gmail.com" }]
maintainers = [{ name = "Eileen Meyer", email = "eileen.meyer@gmail.com" }]
license = { text = "GPL-2.0" }
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.24",
    "scipy>=1.11",
    "scikit-image>=0.22",
    "astropy>=6.0",
    "matplotlib>=3.7",
    "pyregion>=2.2",
    "uncertainties>=3.2",
    "pandas>=2.0",
    "Pillow>=10.0",
    "appdirs>=1.4",
    "imageio>=2.31",
]

[project.optional-dependencies]
ui = ["PyQt5>=5.15"]
dev = ["pytest>=8.0", "ruff>=0.6"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/libwise"]
```

## pyproject template — `packages/wise/pyproject.toml`

```toml
[project]
name = "wisetool"
version = "0.5.0.dev0"
description = "Wavelet Image Segmentation and Evaluation (modernization fork)"
authors = [{ name = "Florent Mertens", email = "flomertens@gmail.com" }]
maintainers = [{ name = "Eileen Meyer", email = "eileen.meyer@gmail.com" }]
license = { text = "GPL-2.0" }
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "libwise",
    "numpy>=1.24",
    "scipy>=1.11",
    "scikit-image>=0.22",
    "astropy>=6.0",
    "matplotlib>=3.7",
    "pyregion>=2.2",
    "uncertainties>=3.2",
    "jsonpickle>=3.0",
    "pandas>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.6"]

[project.scripts]
wise = "wise.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/wise"]
```

---

## Observations from initial scoping

These are things noticed during a brief audit of upstream — not all are
strictly necessary to fix, but flagging so they don't surprise the executor.

- **Code volume:** libwise ~12.6k LOC, wise ~8k LOC. Largest files are
  `libwise/plotutils_ui.py` (1.3k), `libwise/imgutils.py` (1.9k),
  `libwise/colormaps.py` (1.3k, mostly data), `libwise/nputils.py` (3k),
  `wise/matcher.py` (2.3k), `wise/tasks.py` (1.5k). The Qt UI port (phase 5)
  is concentrated in `plotutils_ui.py` and `libwise/app/*`.
- **Rename `ressource/` → `resources/`:** upstream misspells the bundled icon
  directory. Rename it during phase 1 (immediately after the verbatim import
  commit, before 2to3) and `grep -rn ressource packages/` to update every
  reference — likely in `plotutils_ui.py`, `app/*.py`, and any
  `pkg_resources.resource_filename` calls. Commit the rename separately so
  the rest of the diff stays small.
- **`pkg_resources` usage:** `plotutils_ui.py` uses `pkg_resources` (now
  deprecated). Migrate to `importlib.resources` if convenient — it's
  optional cleanup, not a blocker.
- **Includes `appdirs.py` as vendored copy:** upstream vendors `appdirs`
  inside libwise. Replace with the pip-installable `appdirs` (or its
  successor `platformdirs`) and delete the vendored file. Listed in deps.
- **`jsonpickle_numpy.py` in wise** is a custom handler for numpy arrays. It
  predates the upstream `jsonpickle.ext.numpy` extension. Consider replacing
  with `jsonpickle.ext.numpy.register_handlers()`. Defer this; not on the
  critical path.
- **`libwise.scriptshelper`** is used by every `wise/actions/*.py` script. Must
  port cleanly (it's small — ~230 LOC) before any CLI smoke test will work.
- **`from matplotlib.mlab import dist_point_to_segment`** in
  `libwise/app/PolyRegionEditor.py` — that function was removed from
  matplotlib. Copy the implementation inline; it's ~6 lines.
- **`from scipy import misc`** appears in `libwise/imgutils.py`. The exact
  uses (likely `imresize`, `imread`, `imsave`) determine the right
  replacement (skimage / imageio / Pillow).
- **`imghdr`** is called somewhere in `libwise` to sniff image types; replace
  with `PIL.Image.open(path).format` (string like `'PNG'`) or `imageio.v3`
  metadata.
- **Tests:** there are three test files in libwise (`test_nputils.py`,
  `test_imgutils.py`, `test_wtutils.py`). They're the only existing safety
  net — get them green before claiming the port is done.

---

## Sandbox FS gotcha (only if executing in this Cowork session)

If executing inside this Cowork sandbox, note: certain files (notably
anything under a `.git/` directory created by `git clone` directly into the
mount) can't be `rm`-ed due to a mount permission quirk, but `mv` works.
If a previous attempt left a `.trash_rollback/` or similar at the workspace
root, just `mv` it aside or ignore — Claude Code on the user's actual
machine won't hit this.

---

## Definition of done

The migration is "done" when:

1. `conda env create -f environment.yml` from `wise_mertens/` resolves and
   installs both packages cleanly (the `pip:` block produces editable
   installs for `libwise` and `wisetool`).
2. After `conda activate wise`: `python -c "import libwise, wise;
   print(libwise.get_version(), wise.get_version())"` succeeds.
3. `pytest packages/libwise/tests` is green (or each failure is triaged in
   `MIGRATION_NOTES.md` with rationale).
4. `wise --help` lists all the actions discovered from `wise.actions`.
5. `MIGRATION_NOTES.md` has an entry for every non-mechanical substitution.
6. No `grep` for `pymorph`, `ConfigParser`, `from types import NoneType`,
   `scipy.misc`, `scipy.ndimage.{filters,interpolation,measurements,morphology}`,
   or `print [^(]` returns hits.
7. README documents the `conda env create` install path and Python 3.11+
   requirement.

UI parity (PolyRegionEditor, WaveletBrowser, WaveletDenoise, etc.) is
considered "done" if each `python -m wise.actions.<name>` (or the equivalent
launcher) opens its window without throwing on a sample dataset.
