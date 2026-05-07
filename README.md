# wise-wavelets

A Python 3.11+ modernization fork of [flomertens/wise](https://github.com/flomertens/wise)
and its companion library [flomertens/libwise](https://github.com/flomertens/libwise).
Both upstreams target Python 2 and were last released against an earlier
scientific-Python stack; this monorepo ports them together to numpy 2.x,
scipy 1.16, scikit-image ≥0.22, astropy ≥6, matplotlib ≥3.9, and PyQt5.

## Status

Ported. The library imports cleanly and the existing test suite is green:

- `pytest packages/libwise/tests packages/wise/tests` — **51 passed, 8 skipped**.
  The skips are upstream tests that exercised functions which were never
  implemented or were left as `assert False` debug stubs; each is documented
  in `MIGRATION_NOTES.md`.
- `wise --help` enumerates all 12 actions discovered from `wise.actions`.
- `python -c "import libwise, wise; print(libwise.get_version(), wise.get_version())"`
  succeeds.
- The PyQt5 UI modules (`libwise.app.PolyRegionEditor`, `WaveletBrowser`,
  `WaveletDenoise`, …) import cleanly. End-to-end widget instantiation against
  real datasets is the next milestone — flagged as a smoke-test follow-up
  rather than blocking.

## Layout

This is a monorepo containing two installable packages:

- `packages/libwise/` — utilities for plotting, wavelet transforms, image
  processing, and the Qt UI. Distributed on PyPI as `libwise`.
- `packages/wise/` — Wavelet Image Segmentation and Evaluation tool, depending
  on `libwise`. Distributed on PyPI as `wisetool`; installs the `wise`
  command.

Both packages use the `src/` layout and `hatchling` as the build backend.

## Requirements

- Python 3.11+
- conda (recommended) or pip

## Install (development)

```bash
conda env create -f environment.yml
conda activate wise-wavelets
```

The `pip:` block in `environment.yml` installs both in-tree packages editable
into the conda env.

## Credit

The original Python 2 codebase and design are due to Florent Mertens. This
fork tracks the same module structure and CLI surface; see `MIGRATION_NOTES.md`
for the full substitution log (pymorph → scikit-image, scipy submodule
re-homing, numpy 2.x scalar aliases, matplotlib backend rename, PyQt4 → PyQt5,
and per-test triage).

## License

GPL-2.0, inherited from upstream.
