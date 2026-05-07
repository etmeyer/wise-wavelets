# wise

WISE (Wavelet Image Segmentation and Evaluation) detects significant features
in radio interferometric images and recovers velocity fields from
cross-correlation of those regions across multi-epoch observations. This is a
Python 3.11+ modernization fork; the `wise` command-line tool is installed by
the `wisetool` distribution and depends on `libwise`.

Part of [wise-wavelets](https://github.com/eileen-meyer/wise-wavelets).

## Install

This package is developed inside the wise-wavelets monorepo. From the repo
root:

```bash
conda env create -f environment.yml
conda activate wise-wavelets
wise --help
```

That installs `wisetool` editable alongside its dependency `libwise`.
`pyproject.toml` is the source of truth for runtime dependencies.

## Credit

Forked from [flomertens/wise](https://github.com/flomertens/wise); see also
the original [project page](https://flomertens.github.io/wise/) for background
and tutorials. The original Python 2 codebase and design are due to Florent
Mertens; this fork modernizes it for the current scientific-Python stack.

## License

GPL-2.0, inherited from upstream.
