# wise_mertens

A Python 3 modernization fork of [flomertens/wise](https://github.com/flomertens/wise)
and its companion library [flomertens/libwise](https://github.com/flomertens/libwise).
Both upstreams target Python 2; this monorepo ports them together to a current
scientific-Python stack.

## Layout

This is a monorepo containing two installable packages:

- `packages/libwise/` — utilities for plotting, wavelet transforms, image
  processing, and the Qt UI. Published on PyPI as `libwise`.
- `packages/wise/` — Wavelet Image Segmentation and Evaluation tool, depending
  on `libwise`. Published on PyPI as `wisetool`.

Both packages use the `src/` layout and `hatchling` as the build backend.

## Requirements

- Python 3.11+
- conda (recommended) or pip

## Install (development)

```bash
conda env create -f environment.yml
conda activate wise
```

The `pip:` block in `environment.yml` installs both in-tree packages editable
into the conda env.

## Status

Migration in progress. See `MIGRATION_PLAN.md` for the full porting plan and
`MIGRATION_NOTES.md` for the running log of non-mechanical substitutions made
during the port.

## License

GPL-2.0, inherited from upstream.
