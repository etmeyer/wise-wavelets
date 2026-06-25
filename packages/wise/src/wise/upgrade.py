"""Migrate a 0.5/0.6 wise project into the 1.0 on-disk layout.

This module is intentionally **self-contained**: it depends only on the
standard library (plus a local ``import wise`` for the version string when
writing a manifest). It does *not* import ``wise.project``, ``wise.tasks``,
``wise.matcher``, ``wise.wds``, or ``libwise``'s ``BaseConfiguration``
machinery. The point is that this single file could be backported to a
hypothetical ``0.6.x`` maintenance release as a *forward*-migration shim —
users could run it on a 0.6 project before ever installing 1.0 — and that
backport breaks the moment ``upgrade.py`` pulls in a 1.0-only data class.

What it migrates (see :func:`upgrade_project`):

* ``wise_config`` — renames keys per :data:`RENAMED_OPTIONS`, drops keys per
  :data:`REMOVED_OPTIONS`, leaves everything else untouched. Only rewrites
  the file when something actually changed (keeps it idempotent and avoids
  needless mtime churn).
* Result directories — ``<name>/<name>.set.dat`` (the 0.5/0.6 marker) becomes
  a ``<name>.wiseproj/`` bundle with the 1.0 generic file names and a fresh
  ``manifest.json``.
* The project-root marker ``.wise/`` is created if missing.
* ``.gitignore`` gains a ``.wise/`` entry if the file exists and lacks one.

Everything is idempotent: re-running on an already-migrated project is a
no-op. ``dry_run=True`` walks the same paths and reports what *would* happen
without touching disk.
"""
from __future__ import annotations

import configparser
import dataclasses
import datetime
import json
import os
import re
import shutil

# ---------------------------------------------------------------------------
# Static migration tables
# ---------------------------------------------------------------------------
# When wise.* adds new renames or removals, mirror them here. Kept as in-module
# constants (not imported from wise.wds / wise.project) so upgrade.py can be
# backported to 0.6.x without pulling in 1.0-only code. Section names match the
# configparser headers written by BaseConfiguration.to_file.
RENAMED_OPTIONS: dict[str, dict[str, str]] = {
    "Finder configuration": {"alpha_threashold": "alpha_threshold"},
}
REMOVED_OPTIONS: dict[str, set[str]] = {
    "Data configuration": {"data_dir"},
}

# Optional human-readable annotations for specific removals, surfaced in the
# action log so the user understands *why* a key vanished.
_REMOVAL_NOTES: dict[tuple[str, str], str] = {
    ("Data configuration", "data_dir"):
        "no longer needed in 1.0; project root is resolved via .wise/",
}

# ---------------------------------------------------------------------------
# Layout constants (mirror wise.tasks / wise.project; kept local on purpose)
# ---------------------------------------------------------------------------
CONFIG_FILENAME = "wise_config"
MARKER_DIRNAME = ".wise"
BUNDLE_SUFFIX = ".wiseproj"
SCHEMA_VERSION = "1.0"

# Generic file names inside a 1.0 bundle.
_DETECTION_FILE = "detection.dat"
_IMAGE_SET_FILE = "image_set.dat"
_CONFIG_FILE = "config.wise_config"
_LINKS_PREFIX = "links"
_LINKS_SUFFIX = ".dfc.dat"

# Old 0.5/0.6 result-directory constituents (relative to ``<name>/``):
_OLD_DETECTION_EXT = ".ms.dat"
_OLD_IMAGE_SET_EXT = ".set.dat"
_OLD_CONFIG_EXT = ".conf"


def _old_link_re(name: str) -> "re.Pattern[str]":
    """Regex matching a 0.5/0.6 per-scale link file for result ``name``.

    Two suffix spellings exist in the wild and both are accepted:

    * ``<name>_<scale>.dfc.dat``     — single-scale FeaturesLinkBuilder.TYPE
    * ``<name>_<scale>.ms.dfc.dat``  — what 0.6.0's ``save()`` actually wrote
      (it used the MultiScaleFeaturesLinkBuilder default suffix ``.ms.dfc.dat``)

    The scale is captured with ``[0-9.]+`` — the same pattern the 1.0 matcher
    loader uses, so floats like ``4.0`` round-trip. The ``.ms`` infix is
    optional, which is what makes both spellings match.
    """
    return re.compile(
        r"^" + re.escape(name) + r"_([0-9.]+)(?:\.ms)?" + re.escape(_LINKS_SUFFIX) + r"$"
    )


@dataclasses.dataclass
class UpgradeReport:
    """Outcome of an :func:`upgrade_project` run.

    ``configs_renamed`` counts key changes (renames + removals) applied to the
    top-level ``wise_config``. ``results_migrated`` / ``results_skipped`` count
    result directories converted / left alone. ``actions`` is the ordered list
    of human-readable lines for the CLI to echo (each prefixed ``[dry-run] ``
    when ``dry_run`` is set).
    """

    configs_renamed: int = 0
    results_migrated: int = 0
    results_skipped: int = 0
    actions: list[str] = dataclasses.field(default_factory=list)


def upgrade_project(directory: str, dry_run: bool = False) -> UpgradeReport:
    """Migrate a 0.5/0.6 wise project at ``directory`` into 1.0 layout.

    Idempotent: re-running on an already-migrated project is a no-op (no
    errors, nothing rewritten).

    Migrates:
      - wise_config: renames keys per RENAMED_OPTIONS, removes keys per
        REMOVED_OPTIONS, leaves everything else untouched.
      - Result directories: <name>/ containing <name>.set.dat → moves
        constituents into <name>.wiseproj/ with the 1.0 file names and
        writes a fresh manifest.json.
      - Project marker: creates <directory>/.wise/ if missing.
      - .gitignore: appends ``.wise/`` if a .gitignore exists and the
        entry is missing.

    Args:
      directory: absolute or relative path to the 0.5/0.6 project root.
      dry_run: when True, report what would happen but don't write
               anything to disk. Useful for ``wise upgrade-config --dry-run``.

    Returns:
      UpgradeReport with counts (configs_renamed, results_migrated,
      results_skipped) and a list of action lines for the CLI to echo.
    """
    report = UpgradeReport()
    root = os.path.abspath(directory)
    prefix = "[dry-run] " if dry_run else ""

    _migrate_wise_config(root, report, dry_run, prefix)
    _migrate_result_dirs(root, report, dry_run, prefix)
    _ensure_marker(root, report, dry_run, prefix)
    _ensure_gitignore_entry(root, MARKER_DIRNAME + "/", report, dry_run, prefix)

    return report


# ---------------------------------------------------------------------------
# wise_config
# ---------------------------------------------------------------------------

def _migrate_wise_config(root, report, dry_run, prefix):
    path = os.path.join(root, CONFIG_FILENAME)
    if not os.path.isfile(path):
        report.actions.append(
            "%sNo wise_config found at %s; nothing to migrate." % (prefix, path)
        )
        return
    changes, lines = _rewrite_config_file(path, dry_run)
    report.configs_renamed += changes
    if changes:
        report.actions.extend(prefix + line for line in lines)
    else:
        report.actions.append(
            "%swise_config already in 1.0 format; left unchanged." % prefix
        )


def _rewrite_config_file(path, dry_run):
    """Apply RENAMED_OPTIONS / REMOVED_OPTIONS to the config file at ``path``.

    Returns ``(n_changes, action_lines)``. The file is rewritten only when at
    least one key changed and ``dry_run`` is False — so a clean config keeps
    its mtime, which is what makes the whole migration idempotent.
    """
    parser = configparser.RawConfigParser()
    # Preserve key case; the config writer emits lowercase keys but a
    # user-edited file might not, and we shouldn't silently normalize.
    parser.optionxform = str
    parser.read(path)

    changes = 0
    lines = []
    label = os.path.basename(path)
    for section in parser.sections():
        for old_key, new_key in RENAMED_OPTIONS.get(section, {}).items():
            if parser.has_option(section, old_key):
                value = parser.get(section, old_key)
                parser.remove_option(section, old_key)
                parser.set(section, new_key, value)
                changes += 1
                lines.append(
                    "%s: renamed [%s] %s -> %s" % (label, section, old_key, new_key)
                )
        for key in sorted(REMOVED_OPTIONS.get(section, set())):
            if parser.has_option(section, key):
                parser.remove_option(section, key)
                changes += 1
                note = _REMOVAL_NOTES.get((section, key))
                msg = "%s: removed [%s] %s" % (label, section, key)
                if note:
                    msg += " (%s)" % note
                lines.append(msg)

    if changes and not dry_run:
        with open(path, "w") as fh:
            parser.write(fh)
    return changes, lines


# ---------------------------------------------------------------------------
# Result directories
# ---------------------------------------------------------------------------

def _migrate_result_dirs(root, report, dry_run, prefix):
    if not os.path.isdir(root):
        return
    for entry in sorted(os.listdir(root)):
        sub = os.path.join(root, entry)
        if not os.path.isdir(sub) or entry.endswith(BUNDLE_SUFFIX):
            continue
        set_files = sorted(
            f for f in os.listdir(sub) if f.endswith(_OLD_IMAGE_SET_EXT)
        )
        if not set_files:
            # Not a 0.5/0.6 result directory; ignore silently.
            continue
        name = set_files[0][: -len(_OLD_IMAGE_SET_EXT)]
        _migrate_one_result(root, sub, name, report, dry_run, prefix)


def _migrate_one_result(root, sub, name, report, dry_run, prefix):
    dirname = os.path.basename(sub)
    bundle_dir = os.path.join(root, name + BUNDLE_SUFFIX)

    if os.path.isdir(bundle_dir):
        report.actions.append(
            "%sSkipped %s/: %s already exists (already migrated)."
            % (prefix, dirname, name + BUNDLE_SUFFIX)
        )
        report.results_skipped += 1
        return

    ms_file = os.path.join(sub, name + _OLD_DETECTION_EXT)
    if not os.path.isfile(ms_file):
        report.actions.append(
            "%sSkipped %s/: missing %s (incomplete result, not migrating)."
            % (prefix, dirname, name + _OLD_DETECTION_EXT)
        )
        report.results_skipped += 1
        return

    set_file = os.path.join(sub, name + _OLD_IMAGE_SET_EXT)
    conf_file = os.path.join(sub, name + _OLD_CONFIG_EXT)
    has_conf = os.path.isfile(conf_file)

    # Per-scale link files (either suffix spelling). Sorted by numeric scale.
    link_re = _old_link_re(name)
    link_files = []  # (abs_src, scale_str)
    for f in os.listdir(sub):
        m = link_re.match(f)
        if m:
            link_files.append((os.path.join(sub, f), m.group(1)))
    link_files.sort(key=lambda t: float(t[1]))
    scales = [scale for _, scale in link_files]

    # Build the move plan: (src_abs, dest_basename).
    plan = [(ms_file, _DETECTION_FILE), (set_file, _IMAGE_SET_FILE)]
    if has_conf:
        plan.append((conf_file, _CONFIG_FILE))
    for src, scale in link_files:
        plan.append((src, "%s_%s%s" % (_LINKS_PREFIX, scale, _LINKS_SUFFIX)))

    report.actions.append(
        "%sMigrate %s/ -> %s/ (%d file%s%s)"
        % (
            prefix, dirname, name + BUNDLE_SUFFIX, len(plan),
            "" if len(plan) == 1 else "s",
            "; scales " + ", ".join(scales) if scales else "",
        )
    )
    for src, dst in plan:
        report.actions.append(
            "%s  %s -> %s/%s"
            % (prefix, os.path.basename(src), name + BUNDLE_SUFFIX, dst)
        )
    report.results_migrated += 1

    if dry_run:
        return

    os.makedirs(bundle_dir, exist_ok=False)
    for src, dst in plan:
        shutil.move(src, os.path.join(bundle_dir, dst))
    # The bundle config carries the same renamed/removed keys as wise_config.
    if has_conf:
        _rewrite_config_file(os.path.join(bundle_dir, _CONFIG_FILE), dry_run=False)
    _write_manifest(bundle_dir, name, scales, has_conf)
    _rmdir_if_empty(sub, report, prefix)


def _write_manifest(bundle_dir, name, scales, has_conf):
    """Write ``manifest.json`` describing the migrated bundle.

    Mirrors the manifest :func:`wise.tasks.save` writes, so a migrated bundle
    is indistinguishable from a freshly-saved one. ``wise_version`` records the
    version that *ran the migration* (honest about provenance — see roadmap).
    """
    import wise  # local: only wise.__version__ (a string) is needed

    files = {"detection": _DETECTION_FILE, "image_set": _IMAGE_SET_FILE}
    if has_conf:
        files["config"] = _CONFIG_FILE
    files["links"] = ["%s_%s%s" % (_LINKS_PREFIX, s, _LINKS_SUFFIX) for s in scales]

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "name": name,
        "wise_version": wise.__version__,
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "files": files,
    }
    with open(os.path.join(bundle_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)


def _rmdir_if_empty(sub, report, prefix):
    """Remove ``sub`` if empty; otherwise note the leftover files.

    ``shutil.move`` of every recognized constituent leaves the old result
    directory empty in the normal case. If a user dropped extra files in there
    we refuse to delete them — we leave the directory and log what remained,
    rather than letting ``os.rmdir`` raise.
    """
    remaining = sorted(os.listdir(sub))
    if not remaining:
        os.rmdir(sub)
    else:
        report.actions.append(
            "%s  Note: %s/ kept (%d unrecognized file(s) remain: %s)"
            % (prefix, os.path.basename(sub), len(remaining), ", ".join(remaining))
        )


# ---------------------------------------------------------------------------
# Project marker + .gitignore
# ---------------------------------------------------------------------------

def _ensure_marker(root, report, dry_run, prefix):
    marker = os.path.join(root, MARKER_DIRNAME)
    if os.path.isdir(marker):
        return
    report.actions.append("%sCreate project marker %s/" % (prefix, MARKER_DIRNAME))
    if not dry_run:
        os.makedirs(marker, exist_ok=True)


def _ensure_gitignore_entry(directory, entry, report, dry_run, prefix):
    """Append ``entry`` to ``<directory>/.gitignore`` if it exists and lacks it.

    Reproduces the idempotent helper in ``cli.py`` (kept standalone for the
    backport story) with one deliberate difference: a migration must not
    *create* a ``.gitignore`` the user never had — it only appends to an
    existing one. Preserves the file's trailing-newline convention.
    """
    gi_path = os.path.join(directory, ".gitignore")
    if not os.path.exists(gi_path):
        return
    with open(gi_path) as fh:
        content = fh.read()
    existing = {line.strip() for line in content.splitlines() if line.strip()}
    if entry in existing:
        return
    report.actions.append("%sAppend %r to .gitignore" % (prefix, entry))
    if dry_run:
        return
    sep = "" if content.endswith("\n") or content == "" else "\n"
    with open(gi_path, "a") as fh:
        fh.write("%s%s\n" % (sep, entry))
