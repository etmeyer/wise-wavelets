.. _data_formats:

Data file formats
=================

This page documents the plain-text data files WISE reads and writes
outside of FITS images, so that users can hand-author or inspect them
without round-tripping through the Python API.

.. _core_offset_file:

Core offset file (``core.dat``)
-------------------------------

The path pointed to by ``data.core_offset_filename`` (default
``core.dat``, relative to ``data.data_dir``) holds the per-epoch position
of the radio core, which WISE uses to align maps before detection and
matching. The file is parsed by
:meth:`wise.wiseutils.CoreOffsetPositions.new_from_file` and written by
:meth:`wise.wiseutils.CoreOffsetPositions.save`.

Format
~~~~~~

Plain text, whitespace-separated, one row per epoch. Lines beginning
with ``#`` are treated as comments and skipped (NumPy ``loadtxt``
default). No header row is supported by the parser.

============  ==================  ====================================================================================
Column        Type                Meaning
============  ==================  ====================================================================================
1 — epoch     ISO date            Observation date, ``YYYY-MM-DD``. Must match the epoch reported by ``img.get_epoch()``.
2 — id        integer             Reserved; currently unused. Always written as ``0``. Discarded by the parser.
3 — r         float               Radial offset of the core from the map's reference pixel, in ``data.projection_unit``.
4 — pa        float (degrees)     Position angle in degrees, **east of north** (i.e. from celestial north toward east).
============  ==================  ====================================================================================

Internally the row is converted to a Cartesian offset
``(x, y) = (r·sin(pa), r·cos(pa))`` in projection units, and the image
is shifted by ``(-x, -y)`` during alignment.

Annotated example
~~~~~~~~~~~~~~~~~

::

    # Core offsets for 3C 120
    # Units: r in mas (data.projection_unit default), pa in degrees east-of-north.
    # epoch       id   r        pa
    2009-05-13    0    0.124    -68.3
    2009-07-23    0    0.151    -64.9
    2009-10-19    0    0.098    -71.2

Each row aligns a single epoch. Epochs present in the project but absent
from this file are left unshifted (zero offset).

Gotchas
~~~~~~~

These are the three things that most commonly go wrong:

1. **Position angle convention.** PA is degrees east-of-north, the
   standard astrometric convention (from celestial north, increasing
   toward east). It is **not** the major-axis convention used by some
   imaging tools. Wrong-handedness here produces a sign-flipped
   alignment that looks plausibly close but is systematically off.

2. **Units follow** ``data.projection_unit``\ **, not sky coordinates.**
   ``r`` is in the project's projection unit (defaults to ``mas``); it
   is *not* an angular separation in arcsec or degrees. Copying a value
   straight out of a CASA log without unit-converting will silently
   produce nonsense offsets — no error is raised because the value is a
   valid float.

3. **Epoch matching is by image date, not filename.** Rows are keyed by
   ``img.get_epoch()`` (the FITS observation date), so a typo in the
   date column does not error and does not warn — the epoch simply
   fails to match and the image is left unshifted. If maps look
   unaligned despite a populated ``core.dat``, check the dates against
   ``wise info`` output before suspecting the offsets themselves.
