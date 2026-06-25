"""Tests for ``wise.upgrade`` — the 0.5/0.6 → 1.0 migration tool (PR8).

Covers wise_config key rewriting, result-directory → ``.wiseproj`` bundle
conversion, idempotency, dry-run, and the documented edge cases. The module is
stdlib-only and operates on plain files, so these tests need no FITS data —
result constituents are created as files with arbitrary bytes.
"""
import configparser
import json
import os

import pytest

from wise import upgrade


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

def _write(path, content=""):
    with open(path, "w") as fh:
        fh.write(content)


def _make_old_config(directory, alpha_key="alpha_threashold", with_data_dir=True):
    """Write a 0.5/0.6-style wise_config into ``directory``."""
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    parser.add_section("Data configuration")
    parser.set("Data configuration", "fits_extension", "0")
    if with_data_dir:
        parser.set("Data configuration", "data_dir", "/some/old/path")
    parser.add_section("Finder configuration")
    parser.set("Finder configuration", alpha_key, "3")
    parser.set("Finder configuration", "alpha_detection", "4")
    with open(os.path.join(directory, "wise_config"), "w") as fh:
        parser.write(fh)


def _make_old_result(directory, name="result1", scales=("4", "6"),
                     link_suffix=".dfc.dat", with_ms=True, with_conf=True):
    """Create a 0.5/0.6-style ``<name>/`` result directory."""
    rdir = os.path.join(directory, name)
    os.mkdir(rdir)
    _write(os.path.join(rdir, "%s.set.dat" % name), "imageset")
    if with_ms:
        _write(os.path.join(rdir, "%s.ms.dat" % name), "detection")
    if with_conf:
        _write(os.path.join(rdir, "%s.conf" % name),
               "[Finder configuration]\nalpha_threashold = 5\n")
    for scale in scales:
        _write(os.path.join(rdir, "%s_%s%s" % (name, scale, link_suffix)), "links")
    return rdir


def _read_config(path):
    parser = configparser.RawConfigParser()
    parser.optionxform = str
    parser.read(path)
    return parser


# ---------------------------------------------------------------------------
# wise_config rewriting
# ---------------------------------------------------------------------------

def test_config_key_rename(tmp_path):
    _make_old_config(str(tmp_path), with_data_dir=False)
    report = upgrade.upgrade_project(str(tmp_path))

    parser = _read_config(str(tmp_path / "wise_config"))
    assert not parser.has_option("Finder configuration", "alpha_threashold")
    assert parser.get("Finder configuration", "alpha_threshold") == "3"
    # other keys untouched
    assert parser.get("Finder configuration", "alpha_detection") == "4"
    assert parser.get("Data configuration", "fits_extension") == "0"
    assert report.configs_renamed == 1


def test_config_removed_key(tmp_path):
    _make_old_config(str(tmp_path))  # includes data_dir
    upgrade.upgrade_project(str(tmp_path))

    parser = _read_config(str(tmp_path / "wise_config"))
    assert not parser.has_option("Data configuration", "data_dir")
    # the rest survive
    assert parser.get("Data configuration", "fits_extension") == "0"


def test_config_already_clean_not_rewritten(tmp_path):
    _make_old_config(str(tmp_path), alpha_key="alpha_threshold", with_data_dir=False)
    cfg = tmp_path / "wise_config"
    before = cfg.read_text()

    report = upgrade.upgrade_project(str(tmp_path))

    assert report.configs_renamed == 0
    assert cfg.read_text() == before  # byte-identical: not rewritten


def test_config_missing_is_not_an_error(tmp_path):
    report = upgrade.upgrade_project(str(tmp_path))  # greenfield, no config
    assert report.configs_renamed == 0
    assert any("No wise_config found" in line for line in report.actions)


# ---------------------------------------------------------------------------
# result-directory migration
# ---------------------------------------------------------------------------

def test_result_dir_round_trip(tmp_path):
    _make_old_result(str(tmp_path), "result1", scales=("4", "6"))
    report = upgrade.upgrade_project(str(tmp_path))

    bundle = tmp_path / "result1.wiseproj"
    assert bundle.is_dir()
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "detection.dat").is_file()
    assert (bundle / "image_set.dat").is_file()
    assert (bundle / "config.wise_config").is_file()
    assert (bundle / "links_4.dfc.dat").is_file()
    assert (bundle / "links_6.dfc.dat").is_file()

    # old directory is gone (emptied + rmdir'd)
    assert not (tmp_path / "result1").exists()
    assert report.results_migrated == 1
    assert report.results_skipped == 0

    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["schema_version"] == "1.0"
    assert manifest["name"] == "result1"
    assert manifest["files"]["links"] == ["links_4.dfc.dat", "links_6.dfc.dat"]


def test_result_dir_real_060_ms_dfc_suffix(tmp_path):
    """0.6.0's save() wrote links as ``<name>_<scale>.ms.dfc.dat``.

    The migrator must accept that spelling too and rename to
    ``links_<scale>.dfc.dat`` (the prompt's table only listed ``.dfc.dat``).
    """
    _make_old_result(str(tmp_path), "r", scales=("2", "4"), link_suffix=".ms.dfc.dat")
    upgrade.upgrade_project(str(tmp_path))

    bundle = tmp_path / "r.wiseproj"
    assert (bundle / "links_2.dfc.dat").is_file()
    assert (bundle / "links_4.dfc.dat").is_file()
    manifest = json.loads((bundle / "manifest.json").read_text())
    assert manifest["files"]["links"] == ["links_2.dfc.dat", "links_4.dfc.dat"]


def test_bundle_config_keys_migrated(tmp_path):
    """The bundled <name>.conf gets the same key renames applied."""
    _make_old_result(str(tmp_path), "result1", scales=("4",))
    upgrade.upgrade_project(str(tmp_path))

    parser = _read_config(str(tmp_path / "result1.wiseproj" / "config.wise_config"))
    assert parser.get("Finder configuration", "alpha_threshold") == "5"
    assert not parser.has_option("Finder configuration", "alpha_threashold")


def test_idempotency(tmp_path):
    _make_old_config(str(tmp_path))
    _make_old_result(str(tmp_path), "result1", scales=("4",))

    first = upgrade.upgrade_project(str(tmp_path))
    assert first.configs_renamed == 2  # rename + removal
    assert first.results_migrated == 1

    second = upgrade.upgrade_project(str(tmp_path))
    assert second.configs_renamed == 0
    assert second.results_migrated == 0
    assert second.results_skipped == 0


def test_dry_run_writes_nothing(tmp_path):
    _make_old_config(str(tmp_path))
    _make_old_result(str(tmp_path), "result1", scales=("4",))
    cfg_before = (tmp_path / "wise_config").read_text()

    report = upgrade.upgrade_project(str(tmp_path), dry_run=True)

    assert not (tmp_path / "result1.wiseproj").exists()
    assert (tmp_path / "result1").is_dir()  # untouched
    assert not (tmp_path / ".wise").exists()
    assert (tmp_path / "wise_config").read_text() == cfg_before
    # but it still reports what *would* happen, with the [dry-run] prefix
    assert report.results_migrated == 1
    assert all(line.startswith("[dry-run] ") for line in report.actions)


def test_preexisting_bundle_is_skipped(tmp_path):
    _make_old_result(str(tmp_path), "result1", scales=("4",))
    (tmp_path / "result1.wiseproj").mkdir()  # bundle already there

    report = upgrade.upgrade_project(str(tmp_path))

    assert (tmp_path / "result1").is_dir()  # old dir left alone
    assert report.results_skipped == 1
    assert report.results_migrated == 0
    assert any("already exists (already migrated)" in line for line in report.actions)


def test_incomplete_result_is_skipped(tmp_path):
    # .set.dat present but no .ms.dat → incomplete
    _make_old_result(str(tmp_path), "result1", scales=("4",), with_ms=False)

    report = upgrade.upgrade_project(str(tmp_path))

    assert not (tmp_path / "result1.wiseproj").exists()
    assert report.results_skipped == 1
    assert report.results_migrated == 0
    assert any(
        "missing result1.ms.dat" in line and "incomplete" in line
        for line in report.actions
    )


def test_non_result_subdir_ignored(tmp_path):
    (tmp_path / "notaresult").mkdir()
    _write(str(tmp_path / "notaresult" / "readme.txt"), "hi")

    report = upgrade.upgrade_project(str(tmp_path))

    assert (tmp_path / "notaresult").is_dir()
    assert report.results_migrated == 0
    assert report.results_skipped == 0


def test_leftover_files_keep_old_dir(tmp_path):
    """A stray file in the old dir means we can't rmdir it; we keep + note it."""
    _make_old_result(str(tmp_path), "result1", scales=("4",))
    _write(str(tmp_path / "result1" / "stray.txt"), "keep me")

    report = upgrade.upgrade_project(str(tmp_path))

    assert (tmp_path / "result1.wiseproj").is_dir()  # still migrated
    assert (tmp_path / "result1").is_dir()  # but old dir kept
    assert (tmp_path / "result1" / "stray.txt").is_file()
    assert any("unrecognized file" in line for line in report.actions)


# ---------------------------------------------------------------------------
# marker + .gitignore
# ---------------------------------------------------------------------------

def test_greenfield_creates_marker_and_updates_gitignore(tmp_path):
    _write(str(tmp_path / ".gitignore"), "*.pyc\n")

    report = upgrade.upgrade_project(str(tmp_path))

    assert (tmp_path / ".wise").is_dir()
    assert ".wise/" in (tmp_path / ".gitignore").read_text()
    # nothing migrated
    assert report.configs_renamed == 0
    assert report.results_migrated == 0


def test_gitignore_append_when_missing_entry(tmp_path):
    _write(str(tmp_path / ".gitignore"), "*.pyc\nbuild/\n")
    upgrade.upgrade_project(str(tmp_path))
    lines = (tmp_path / ".gitignore").read_text().splitlines()
    assert ".wise/" in lines
    assert lines.count(".wise/") == 1


def test_gitignore_unchanged_when_entry_present(tmp_path):
    _write(str(tmp_path / ".gitignore"), "*.pyc\n.wise/\n")
    before = (tmp_path / ".gitignore").read_text()
    upgrade.upgrade_project(str(tmp_path))
    assert (tmp_path / ".gitignore").read_text() == before


def test_no_gitignore_is_not_created(tmp_path):
    """A migration must not litter a .gitignore the user never had."""
    upgrade.upgrade_project(str(tmp_path))
    assert not (tmp_path / ".gitignore").exists()


def test_marker_not_created_in_dry_run(tmp_path):
    upgrade.upgrade_project(str(tmp_path), dry_run=True)
    assert not (tmp_path / ".wise").exists()
