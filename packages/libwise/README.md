# libwise

Utilities for plotting, wavelet transforms, image processing, and a PyQt5 UI
toolkit. Originally a spin-off of the Wavelet Image Segmentation and Evaluation
(WISE) software; this is a Python 3.11+ modernization fork.

Part of [wise-wavelets](https://github.com/eileen-meyer/wise-wavelets).

## Install

This package is developed inside the wise-wavelets monorepo. From the repo
root:

```bash
conda env create -f environment.yml
conda activate wise-wavelets
```

That installs `libwise` editable alongside its sibling `wisetool` package.
`pyproject.toml` is the source of truth for runtime dependencies; the `[ui]`
extra adds PyQt5 for the Qt-based widgets in `libwise.app`.

## Credit

Forked from [flomertens/libwise](https://github.com/flomertens/libwise). The
original Python 2 codebase and design are due to Florent Mertens; this fork
modernizes it for the current scientific-Python stack.

## License

GPL-2.0, inherited from upstream.
