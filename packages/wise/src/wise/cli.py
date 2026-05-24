"""Entry point for the `wise` command."""
from __future__ import annotations

import logging
import os
import re
import sys
import warnings

import click
from astropy.wcs import FITSFixedWarning

import wise
from wise.actions import actions


def _finder_widths_footer(config) -> str:
    """Return the 'Resulting widths' line for the finder settings section."""
    from wise import wds as _wds
    min_scale = config.finder.get("min_scale")
    max_scale = config.finder.get("max_scale")
    wavelet = config.finder.get("wd_wavelet")
    use_iwd = config.finder.get("use_iwd")
    widths = _wds.compute_scales_widths(min_scale, max_scale, wavelet)
    widths_disp = [int(w) if w == int(w) else w for w in widths]
    if use_iwd:
        iwd_wavelet = config.finder.get("iwd_wavelet")
        wavelet_desc = "wavelet=%s+%s, use_iwd=True" % (wavelet, iwd_wavelet)
    else:
        wavelet_desc = "wavelet=%s, use_iwd=False" % wavelet
    return "Resulting widths: %s px  (%s)" % (widths_disp, wavelet_desc)


def _setup_logging(verbose: bool, quiet: bool, debug: bool) -> None:
    if sum([verbose, quiet, debug]) > 1:
        raise click.UsageError("--verbose, --quiet, and --debug are mutually exclusive")

    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    elif quiet:
        level = logging.ERROR
    else:
        level = logging.WARNING

    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
        force=True,
    )
    logging.captureWarnings(True)
    # E5: silence astropy's per-file FITS-spec drift warning
    warnings.filterwarnings("ignore", category=FITSFixedWarning)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--verbose", "-v", is_flag=True, default=False,
              help="Enable INFO-level logging.")
@click.option("--quiet", "-q", is_flag=True, default=False,
              help="Suppress all but ERROR-level logging.")
@click.option("--debug", is_flag=True, default=False,
              help="Enable DEBUG-level logging.")
@click.option("--non-interactive", is_flag=True, default=False,
              help="Error instead of prompting; combine with per-flag options.")
@click.version_option(version=wise.get_version(), prog_name="wise")
@click.pass_context
def cli(
    ctx: click.Context,
    verbose: bool,
    quiet: bool,
    debug: bool,
    non_interactive: bool,
) -> None:
    """WISE: Wavelet Image Segmentation and Evaluation.

    Run 'wise COMMAND --help' for per-command options.
    """
    _setup_logging(verbose, quiet, debug)
    ctx.ensure_object(dict)
    ctx.obj["non_interactive"] = non_interactive
    ctx.obj["quiet"] = quiet


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("directory", type=click.Path(file_okay=False), default=".")
@click.pass_context
def init(ctx: click.Context, directory: str) -> None:
    """Initialize a wise project in DIRECTORY (default: cwd).

    Creates DIRECTORY/.wise/ (the project-root marker, also used for
    caches and result bundles) and, if absent, DIRECTORY/wise_config
    seeded with the default AnalysisConfiguration. Refuses to
    re-initialize an existing .wise/.
    """
    abspath = os.path.abspath(directory)
    os.makedirs(abspath, exist_ok=True)
    marker = os.path.join(abspath, ".wise")
    try:
        os.makedirs(marker, exist_ok=False)
    except FileExistsError:
        raise click.UsageError(
            f"{directory}/.wise already exists; this looks like an existing "
            f"wise project. Refusing to re-initialize."
        )

    config_path = os.path.join(abspath, actions.CONFIG_FILE)
    if os.path.exists(config_path):
        summary = "(found existing wise_config; added .wise/)"
    else:
        wise.AnalysisConfiguration().to_file(config_path)
        summary = "(created wise_config + .wise/)"

    _ensure_gitignore_entry(abspath, ".wise/")

    click.echo(f"Initialized wise project at {abspath}")
    click.echo(summary)


def _ensure_gitignore_entry(directory: str, entry: str) -> None:
    """Append ``entry`` to ``<directory>/.gitignore`` if not already listed.

    Creates the file if missing. Idempotent — re-runs do not duplicate the
    entry. Preserves the existing trailing-newline convention (or lack
    thereof) of the file.
    """
    gi_path = os.path.join(directory, ".gitignore")
    if os.path.exists(gi_path):
        with open(gi_path) as fh:
            content = fh.read()
        existing = {line.strip() for line in content.splitlines() if line.strip()}
        if entry in existing:
            return
        prefix = "" if content.endswith("\n") or content == "" else "\n"
        with open(gi_path, "a") as fh:
            fh.write(f"{prefix}{entry}\n")
    else:
        with open(gi_path, "w") as fh:
            fh.write(f"{entry}\n")


# ---------------------------------------------------------------------------
# project
# ---------------------------------------------------------------------------

@cli.command()
@click.pass_context
def project(ctx: click.Context) -> None:
    """Print the resolved project root and exit.

    Errors with the standard 'no project root found' UsageError when the
    cwd has no .wise/ ancestor — the same error path as any other
    project-requiring command.
    """
    root = wise.find_project_root()
    if root is None:
        raise wise.ProjectRootNotFound(
            f"no project root found in {os.getcwd()}; run "
            f"`wise init` to create one, or cd into a directory "
            f"with a .wise/"
        )
    click.echo(root)


# ---------------------------------------------------------------------------
# stack
# ---------------------------------------------------------------------------

def _renamed_nsigma_connected(ctx, param, value):
    """Migration callback for the removed ``--nsigma_connected`` flag (A4).

    Hidden option: when the old flag is passed, error with a clear rename
    message instead of click's generic "no such option".
    """
    if value:
        raise click.UsageError(
            "--nsigma_connected was renamed to --keep_brightest_only in "
            "wise 1.0. Update your scripts. If you have saved CLI configs "
            "or shell aliases, run `wise upgrade-config`."
        )
    # value=False means the flag wasn't passed; nothing to do.


@cli.command()
@click.argument("files", nargs=-1, required=True)
@click.option("--output", "-o", default="stack_img.fits", show_default=True,
              help="Output file name.")
@click.option("--nsigma", "-n", default=0.0, type=float, show_default=True,
              help="Clip background below NSIGMA level.")
@click.option("--nsigma_connected", is_flag=True, hidden=True,
              callback=_renamed_nsigma_connected, expose_value=False)
@click.option("--keep_brightest_only", "-c", is_flag=True, default=False,
              help="Discard everything except the brightest connected blob "
                   "(default behaviour is the union of all pixels above σ). "
                   "Renamed from --nsigma_connected in 1.0.")
@click.pass_context
def stack(
    ctx: click.Context,
    files: tuple[str, ...],
    output: str,
    nsigma: float,
    keep_brightest_only: bool,
) -> None:
    """Stack images."""
    import logging as _logging
    _logger = _logging.getLogger(__name__)
    config = actions.get_config(False)
    context = wise.AnalysisContext(config)
    actions.select_files(context, list(files))
    stack_img = context.build_stack_image(
        preprocess=False, nsigma=nsigma, keep_brightest_only=keep_brightest_only
    )
    stack_img.save(output)
    _logger.info("Stacked images saved to %s", output)


# ---------------------------------------------------------------------------
# settings
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("args", nargs=-1)
@click.pass_context
def settings(ctx: click.Context, args: tuple[str, ...]) -> None:
    """Set and get WISE configuration.

    \b
    wise settings set SECTION.OPTION=VALUE [SECTION.OPTION=VALUE ...]
    wise settings get/show [SECTION[.OPTION]]
    wise settings doc [SECTION[.OPTION]]
    wise settings restore CONFIG_FILE
    """
    import re as _re

    import astropy.units as u
    from libwise import imgutils, uiutils

    non_interactive = ctx.obj.get("non_interactive", False)

    if wise.find_project_root() is None:
        raise wise.ProjectRootNotFound(
            f"no project root found in {os.getcwd()}; run "
            f"`wise init` to create one, or cd into a directory "
            f"with a .wise/"
        )

    config = actions.get_config(True)
    args = list(args)

    def _get_section(section_name: str):
        if section_name not in ("data", "finder", "matcher"):
            raise click.UsageError(
                "SECTION must be one of data, finder or matcher"
            )
        return getattr(config, section_name)

    def _check_option(section, option: str) -> None:
        if not section.has(option):
            raise click.UsageError(
                "option %s of %s does not exist" % (option, section.get_title())
            )

    def _delta_range_filter_handler() -> None:
        if non_interactive:
            raise click.UsageError(
                "matcher.delta_range_filter requires interactive input; "
                "pass --non-interactive only with fully automated option sets"
            )
        current_filter = config.matcher.delta_range_filter
        append = False
        click.echo("Current delta range filter: %s" % current_filter)
        if current_filter is not None:
            append = click.confirm(
                "Do you want to add a new delta range filter to the existing one?"
            )

        region = None
        if click.confirm("Restrict delta range filter to a region?"):
            region_filename = uiutils.open_file()
            try:
                region = imgutils.Region(region_filename)
            except Exception:
                click.echo("Warning: opening region file failed")
        if region is not None:
            click.echo("Delta range filter for region: %s" % region.get_name())

        str2vector = lambda s: [float(k) for k in _re.findall("[-0-9.]+", s)]
        check_vector = lambda s: len(str2vector(s)) == 2

        unit = u.Unit(click.prompt("Velocity unit"))
        direction_str = click.prompt("Direction vector (default=[1,0])", default="1,0")
        direction = str2vector(direction_str)
        vx_str = click.prompt("Velocity range in X direction")
        while not check_vector(vx_str):
            vx_str = click.prompt("Velocity range in X direction (need 2 numbers)")
        vx = str2vector(vx_str)
        vy_str = click.prompt("Velocity range in Y direction")
        while not check_vector(vy_str):
            vy_str = click.prompt("Velocity range in Y direction (need 2 numbers)")
        vy = str2vector(vy_str)

        range_filter = wise.DeltaRangeFilter(
            vxrange=vx, vyrange=vy, unit=unit, pix_limit=4, x_dir=direction
        )
        if region is not None:
            range_filter = wise.DeltaRegionFilter(wise.RegionFilter(region), range_filter)
        if append:
            range_filter = current_filter & range_filter

        click.echo("Setting delta_range_filter to: %s" % range_filter)
        config.matcher.delta_range_filter = range_filter

    def _show_issues_banner() -> None:
        issues = config.validate()
        if issues:
            click.echo()
            click.echo("⚠ Configuration issues:")
            for issue in issues:
                click.echo("  • %s" % issue)

    def _show_project_root_header() -> None:
        try:
            root = ctx.obj.get("project_root") or wise.find_project_root()
        except Exception:
            return
        if root is not None:
            click.echo(f"Project root: {root}")
            click.echo()

    if len(args) == 0 or args[0] in ("get", "show"):
        _show_project_root_header()
        if len(args) < 2:
            parts = [
                config.data.values(),
                config.finder.values(),
                _finder_widths_footer(config),
                config.matcher.values(),
            ]
            click.echo("\n".join(parts))
        elif "." in args[1]:
            section_name, option = args[1].split(".", 2)
            section = _get_section(section_name)
            _check_option(section, option)
            click.echo("%s: %s" % (args[1], section.get(option, encode=True)))
        else:
            section = _get_section(args[1])
            click.echo(section.values())
            if args[1] == "finder":
                click.echo(_finder_widths_footer(config))
        _show_issues_banner()

    elif args[0] == "set":
        for arg in args[1:]:
            if arg == "matcher.delta_range_filter":
                _delta_range_filter_handler()
                continue
            try:
                full_option, value = arg.split("=", 2)
                section_name, option = full_option.split(".", 2)
            except Exception:
                raise click.UsageError(
                    "Setting option must be of the form SECTION.OPTION=VALUE"
                )
            section = _get_section(section_name)
            _check_option(section, option)
            click.echo("Setting %s to %s" % (full_option, value))
            section.set(option, value, decode=True)
        if len(args[1:]) > 0:
            config.to_file(actions.get_config_path())
            click.echo("Configuration saved")

    elif args[0] == "doc":
        import warnings as _warnings
        _warnings.warn(
            "'wise settings doc' is deprecated and will be removed in wise 1.0. "
            "Use 'wise settings show' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if len(args) == 1:
            click.echo(config.doc())
        elif "." in args[1]:
            section_name, option = args[1].split(".", 2)
            section = _get_section(section_name)
            _check_option(section, option)
            click.echo(section.doc())
        else:
            section = _get_section(args[1])
            click.echo(section.doc())
        _show_issues_banner()

    elif args[0] == "restore":
        import os as _os
        if len(args) != 2 or not _os.path.isfile(args[1]):
            raise click.UsageError("An existing CONFIG_FILE is required")
        try:
            config.from_file(args[1])
            config.to_file(actions.get_config_path())
        except Exception:
            raise click.UsageError(
                "Restoring configuration from %s failed" % args[1]
            )
        click.echo("Configuration restored from %s" % args[1])

    else:
        raise click.UsageError(
            "Unknown action %r. Expected: set, get, show, doc, restore" % args[0]
        )


# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("files", nargs=-1, required=True)
@click.option("--name", default=None,
              help="Name for saving the result (skips save-name prompt).")
@click.option("--save/--no-save", default=None,
              help="Whether to save the result (skips save prompt).")
@click.option("--view-scales", default=None,
              help="Comma-separated scales to view after detection (skips view loop).")
@click.option("--dry-run", is_flag=True, default=False,
              help="Preview detection on a single file: print per-scale peak counts "
                   "at the configured threshold vs at α=1.5, without running "
                   "segmentation or saving anything.")
@click.pass_context
def detect(
    ctx: click.Context,
    files: tuple[str, ...],
    name: str | None,
    save: bool | None,
    view_scales: str | None,
    dry_run: bool,
) -> None:
    """Run the Segmented wavelet decomposition."""
    import logging as _logging
    _logger = _logging.getLogger(__name__)
    non_interactive = ctx.obj.get("non_interactive", False)

    config = actions.get_config(True)
    context = wise.AnalysisContext(config)

    if dry_run:
        if len(files) != 1:
            raise click.UsageError(
                "--dry-run requires exactly one input file; got %d" % len(files)
            )
        file = files[0]
        alpha_detection = config.finder.get("alpha_detection")
        click.echo(
            "Detection preview for %s (α_detection = %s):"
            % (os.path.basename(file), alpha_detection)
        )
        stats = wise.tasks.detection_preview(context, file)
        header = [
            "Scale (level)",
            "Width (px)",
            "σ_noise",
            "Above α=%s (current)" % alpha_detection,
            "Between α=1.5 and α=%s" % alpha_detection,
        ]
        from libwise import nputils as _nputils
        rows = [
            [s["scale"], s["width"], "%.4g" % s["noise"], s["n_above"], s["n_between"]]
            for s in stats
        ]
        click.echo(_nputils.format_table(rows, header))
        click.echo(
            "Tip: if 'Above α=...' is mostly 0 but 'Between' is nonzero, your "
            "alpha_detection may be too strict for this source. Try "
            "`wise settings set finder.alpha_detection=2.0` and re-run dry-run."
        )
        return

    actions.select_files(context, list(files))

    if len(context.files) == 0:
        return

    wise.tasks.detection_all(context)

    str2vector = lambda s: [float(k) for k in re.findall("[-0-9.]+", s)]

    # View-scales: flag → one shot; no flag → interactive loop (skipped in non-interactive)
    if view_scales is not None:
        scales = str2vector(view_scales)
        valid = wise.tasks._get_scales(scales, context.result.get_scales())
        if valid:
            wise.tasks.view_wds(context, scales=valid)
        else:
            _logger.warning(
                "No valid scales in %s. Available: %s",
                view_scales,
                context.result.get_scales(),
            )
    elif not non_interactive:
        check = lambda s: len(
            wise.tasks._get_scales(str2vector(s), context.result.get_scales())
        ) > 0
        txt = "View scales (available: %s) (press enter to leave)" % (
            context.result.get_scales(),
        )
        while True:
            scales_str = click.prompt(txt, default="")
            if not scales_str:
                break
            if check(scales_str):
                wise.tasks.view_wds(context, scales=str2vector(scales_str))
            else:
                click.echo(
                    "No valid scales. Available: %s" % context.result.get_scales()
                )

    # Save decision
    if save is None:
        if non_interactive:
            raise click.UsageError(
                "--save or --no-save is required in non-interactive mode"
            )
        save = click.confirm(
            "Save detection for plotting only? (1.0 bundles cannot be re-matched.)"
        )

    if save:
        if name is None:
            if non_interactive:
                raise click.UsageError(
                    "--name is required in non-interactive mode when saving"
                )
            name = click.prompt("Name", default="result")
        wise.tasks.save(context, name)
        saved_path = os.path.abspath(
            os.path.join(context.get_data_dir(), name + ".wiseproj"))
        click.echo("Saved to %s/" % saved_path)


# ---------------------------------------------------------------------------
# match
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("files", nargs=-1, required=True)
@click.option("--name", default=None,
              help="Name for saving the result (skips save-name prompt).")
@click.option("--save/--no-save", default=None,
              help="Whether to save the result (skips save prompt).")
@click.option("--view-scales", default=None,
              help="Scale to view after matching (skips view loop).")
@click.pass_context
def match(
    ctx: click.Context,
    files: tuple[str, ...],
    name: str | None,
    save: bool | None,
    view_scales: str | None,
) -> None:
    """Run the matching procedure."""
    import logging as _logging
    from libwise import nputils

    _logger = _logging.getLogger(__name__)
    non_interactive = ctx.obj.get("non_interactive", False)

    # A2: `wise match` re-runs detection before matching. The .wiseproj bundle
    # only persists feature centroids, so a saved detection cannot be re-matched
    # in 1.0. Always inform the user (click.echo, not logger.info — suppressible
    # via --quiet but on by default).
    if not ctx.obj.get("quiet", False):
        click.echo(
            "Note: 'wise match' re-runs detection with the current finder.* "
            "settings before matching. The .wiseproj bundle layout in this "
            "release saves feature centroids only; re-matching a saved "
            "detection isn't supported in 1.0 (planned for a future release). "
            "If you want matching with different finder settings, change "
            "finder.* in wise_config and re-run `wise match`."
        )

    config = actions.get_config(True)
    context = wise.AnalysisContext(config)
    actions.select_files(context, list(files))

    if len(context.files) == 0:
        return

    wise.tasks.match_all(context)

    # View-scales: flag → one shot; no flag → interactive loop (skipped in non-interactive)
    if view_scales is not None:
        try:
            scale = float(view_scales)
        except ValueError:
            raise click.UsageError("--view-scales must be a single numeric scale value")
        if scale in context.result.get_scales():
            wise.tasks.view_displacements(context, scale)
        else:
            _logger.warning(
                "Scale %s not available. Available: %s",
                scale,
                context.result.get_scales(),
            )
    elif not non_interactive:
        check = lambda s: nputils.is_str_number(s) and float(s) in context.result.get_scales()
        txt = "View scales (available: %s) (press enter to leave)" % (
            context.result.get_scales(),
        )
        while True:
            scale_str = click.prompt(txt, default="0")
            if not scale_str or scale_str == "0":
                break
            if check(scale_str):
                wise.tasks.view_displacements(context, float(scale_str))
            else:
                click.echo(
                    "Scale not available. Available: %s" % context.result.get_scales()
                )

    # Save decision
    if save is None:
        if non_interactive:
            raise click.UsageError(
                "--save or --no-save is required in non-interactive mode"
            )
        save = click.confirm("Save matched result?")

    if save:
        if name is None:
            if non_interactive:
                raise click.UsageError(
                    "--name is required in non-interactive mode when saving"
                )
            name = click.prompt("Name", default="result")
        wise.tasks.save(context, name)
        saved_path = os.path.abspath(
            os.path.join(context.get_data_dir(), name + ".wiseproj"))
        click.echo("Saved to %s/" % saved_path)


# ---------------------------------------------------------------------------
# region
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("img_file")
@click.argument("reg_file", required=False, default=None)
@click.pass_context
def region(ctx: click.Context, img_file: str, reg_file: str | None) -> None:
    """View and create DS9-type region files."""
    import os
    from libwise import imgutils
    from libwise.app import PolyRegionEditor

    img = imgutils.guess_and_open(img_file)
    editor = PolyRegionEditor.PolyRegionEditor(
        img, current_folder=os.path.dirname(img.file)
    )
    if reg_file:
        poly_region = imgutils.PolyRegion.from_file(
            reg_file, img.get_coordinate_system()
        )
        editor.load_poly_region(poly_region)
    editor.start()


# ---------------------------------------------------------------------------
# select_files
# ---------------------------------------------------------------------------

@cli.command("select_files")
@click.argument("files", nargs=-1, required=True)
@click.option("--output", "-o", default="files", show_default=True,
              help="Output file name.")
@click.option("--start-date", "-s", default=None,
              help="Reject files with date < START (YYYY-MM-DD).")
@click.option("--end-date", "-e", default=None,
              help="Reject files with date > END (YYYY-MM-DD).")
@click.option("--filter-date", "-f", "filter_dates_raw", multiple=True,
              help="Reject files with date == DATE (YYYY-MM-DD; repeatable).")
@click.pass_context
def select_files_cmd(
    ctx: click.Context,
    files: tuple[str, ...],
    output: str,
    start_date: str | None,
    end_date: str | None,
    filter_dates_raw: tuple[str, ...],
) -> None:
    """Build a sorted list of FITS files and write it to OUTPUT."""
    from libwise import imgutils, nputils

    def _parse_date(raw: str | None, option: str):
        if raw is None:
            return None
        d = nputils.guess_date(raw, ["%Y-%m-%d", "%Y_%m_%d"])
        if d is None:
            raise click.UsageError(
                "Invalid date format for %s: %r (expected YYYY-MM-DD)" % (option, raw)
            )
        return d

    start = _parse_date(start_date, "--start-date")
    end = _parse_date(end_date, "--end-date")
    fdates = [_parse_date(d, "--filter-date") for d in filter_dates_raw]

    result_files = imgutils.fast_sorted_fits(
        list(files), start_date=start, end_date=end, filter_dates=fdates
    )

    click.echo("Outputting %s files in '%s'" % (len(result_files), output))
    with open(output, "w") as fh:
        fh.write("\n".join(result_files) + "\n")


# ---------------------------------------------------------------------------
# plot group: kinematic charts derived from saved results
# ---------------------------------------------------------------------------

@cli.group()
def plot() -> None:
    """Kinematic charts derived from saved results."""


@plot.command("features")
@click.argument("name")
@click.argument("scales")
@click.option("--pa", "-p", is_flag=True, default=False,
              help="Additionally plot positional angle vs epoch.")
@click.pass_context
def plot_features(ctx: click.Context, name: str, scales: str, pa: bool) -> None:
    """Plot all features on a distance-from-core vs epoch chart.

    NAME is the saved result name; SCALES is a comma-separated list.
    """
    import logging as _logging
    from libwise import nputils

    _logger = _logging.getLogger(__name__)

    context = actions.load(name)
    if context is None:
        raise click.UsageError("No results saved with name %r" % name)

    try:
        scale_list = nputils.str2floatlist(scales)
    except Exception:
        raise click.UsageError(
            "Invalid scales %r. Available: %s" % (scales, context.result.get_scales())
        )

    _logger.info("Plotting features from scales %s", scale_list)
    wise.tasks.plot_all_features(context, scale_list, pa=pa)


@plot.command("links")
@click.argument("name")
@click.argument("scales")
@click.option("--min-link-size", "-m", default=2, type=float, show_default=True,
              help="Filter out links with size < N.")
@click.pass_context
def plot_links(
    ctx: click.Context, name: str, scales: str, min_link_size: float
) -> None:
    """Plot all component trajectories on the reference map.

    NAME is the saved result name; SCALES is a comma-separated list.
    """
    from libwise import nputils

    context = actions.load(name)
    if context is None:
        raise click.UsageError("No results saved with name %r" % name)

    try:
        scale_list = nputils.str2floatlist(scales)
    except Exception:
        raise click.UsageError(
            "Invalid scales %r. Available: %s" % (scales, context.result.get_scales())
        )

    wise.tasks.view_links(context, scales=scale_list, min_link_size=min_link_size)


@plot.command("sep")
@click.argument("name")
@click.argument("scales")
@click.option("--pa", "-p", is_flag=True, default=False,
              help="Additionally plot positional angle vs epoch.")
@click.option("--fit", "-f", is_flag=True, default=False,
              help="Fit each link with a linear function.")
@click.option("--num", "-n", is_flag=True, default=False,
              help="Annotate each link.")
@click.option("--min-link-size", "-m", default=2, type=float, show_default=True,
              help="Filter out links with size < N.")
@click.pass_context
def plot_sep(
    ctx: click.Context,
    name: str,
    scales: str,
    pa: bool,
    fit: bool,
    num: bool,
    min_link_size: float,
) -> None:
    """Plot separation from core with time.

    NAME is the saved result name; SCALES is a comma-separated list.
    """
    from libwise import nputils

    context = actions.load(name)
    if context is None:
        raise click.UsageError("No results saved with name %r" % name)

    try:
        scale_list = nputils.str2floatlist(scales)
    except Exception:
        raise click.UsageError(
            "Invalid scales %r. Available: %s" % (scales, context.result.get_scales())
        )

    fit_fct = nputils.LinearFct if fit else None
    fit_result = wise.tasks.plot_separation_from_core(
        context, scales=scale_list, num=num,
        min_link_size=min_link_size, fit_fct=fit_fct, pa=pa
    )
    if fit and fit_result:
        for link, fct in fit_result.items():
            click.echo(
                "Fit result for link %s: %.2f +- %.2f mas / year"
                % (link.get_id(), fct.a, fct.ea)
            )


# ---------------------------------------------------------------------------
# show group: sky-map renderings and tabular information
# ---------------------------------------------------------------------------

@cli.group()
def show() -> None:
    """Sky-map renderings and tabular information."""


@show.command("features")
@click.argument("name")
@click.argument("scales")
@click.pass_context
def show_features(ctx: click.Context, name: str, scales: str) -> None:
    """Plot all features location on the reference image.

    NAME is the saved result name; SCALES is a comma-separated list.
    """
    import logging as _logging
    from libwise import nputils

    _logger = _logging.getLogger(__name__)

    context = actions.load(name)
    if context is None:
        raise click.UsageError("No results saved with name %r" % name)

    try:
        scale_list = nputils.str2floatlist(scales)
    except Exception:
        raise click.UsageError(
            "Invalid scales %r. Available: %s" % (scales, context.result.get_scales())
        )

    _logger.info("Plotting features from scales %s", scale_list)
    wise.tasks.view_all_features(context, scale_list)


@show.command("image")
@click.argument("files", nargs=-1, required=True)
@click.option("--no-crop", "-n", "no_crop", is_flag=True, default=False,
              help="Do not crop images according to data.roi_coords.")
@click.option("--no-align", is_flag=True, default=False,
              help="Do not align images according to data.core_offset_filename.")
@click.option("--show-mask", "-m", is_flag=True, default=False,
              help="Overplot the mask if it exists.")
@click.option("--reg-file", "-r", "reg_files", multiple=True,
              help="Region file(s) to overplot (repeatable).")
@click.pass_context
def show_image(
    ctx: click.Context,
    files: tuple[str, ...],
    no_crop: bool,
    no_align: bool,
    show_mask: bool,
    reg_files: tuple[str, ...],
) -> None:
    """Simple image viewer."""
    from libwise import imgutils

    preprocess = not no_crop
    align = not no_align
    regions = []
    for f in reg_files:
        try:
            regions.append(imgutils.Region(f))
        except Exception:
            raise click.UsageError("Failed to read region file: %s" % f)

    config = actions.get_config(False)
    context = wise.AnalysisContext(config)
    actions.select_files(context, list(files))
    wise.tasks.view_all(
        context, preprocess=preprocess, show_regions=regions,
        show_mask=show_mask, align=align
    )


@show.command("info")
@click.argument("files", nargs=-1, required=False)
@click.option("--velocity", "-V", is_flag=True, default=False,
              help="Report velocity resolution instead of beam/pixel info.")
@click.pass_context
def show_info(
    ctx: click.Context,
    files: tuple[str, ...],
    velocity: bool,
) -> None:
    """Give information on beam, pixel scales or velocity resolution."""
    if not files:
        raise click.UsageError("Missing argument 'FILES...'")

    config = actions.get_config(False)
    context = wise.AnalysisContext(config)
    actions.select_files(context, list(files))
    if velocity:
        wise.tasks.info_files_delta(context)
    else:
        wise.tasks.info_files(context)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    cli()
