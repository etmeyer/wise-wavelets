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
