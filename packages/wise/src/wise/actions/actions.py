import logging
import os

import click
from libwise import imgutils
from libwise.nputils import OptionRenamedError

import wise

CONFIG_FILE = 'wise_config'

logger = logging.getLogger(__name__)


def get_config_path():
    """Return the absolute path where wise_config lives for the current project.

    Raises :class:`wise.ProjectRootNotFound` when no project root is resolved.
    """
    root = wise.find_project_root()
    if root is None:
        raise wise.ProjectRootNotFound(
            f"no project root found in {os.getcwd()}; run "
            f"`wise init` to create one, or cd into a directory "
            f"with a .wise/"
        )
    return os.path.join(root, CONFIG_FILE)


def get_config(create_if_none=False):
    config = wise.AnalysisConfiguration()
    root = wise.find_project_root()
    # Not every command needs a project root (e.g. `wise init`, `wise --help`);
    # let the caller error via get_data_dir / get_config_path if they need it.
    if root is None:
        return config
    config_path = os.path.join(root, CONFIG_FILE)
    if os.path.exists(config_path):
        try:
            config.from_file(config_path)
        except OptionRenamedError as e:
            raise click.UsageError(
                "`%s` was renamed to `%s` in wise 1.0. "
                "Run `wise upgrade-config` to migrate your saved wise_config."
                % (e.old_name, e.new_name)
            )
    elif create_if_none:
        config.to_file(config_path)

    for issue in config.validate():
        logger.warning("Configuration issue: %s", issue)

    return config


def select_files(ctx, args):
    if imgutils.is_fits(args[0]) or imgutils.is_img(args[0]):
        ctx.select_files(args)
    else:
        with open(args[0]) as file:
            ctx.select_files([k.strip() for k in file.readlines()])


def load(name):
    config = get_config(False)

    root = wise.find_project_root()
    if root is None:
        raise wise.ProjectRootNotFound(
            f"no project root found in {os.getcwd()}; run "
            f"`wise init` to create one, or cd into a directory "
            f"with a .wise/"
        )

    bundle_path = wise.tasks._bundle_path(root, name)
    if not os.path.isdir(bundle_path):
        # Raises a UsageError, enriched if an old-format result dir is present.
        wise.tasks._raise_no_bundle(root, name)

    manifest = wise.tasks._read_manifest(bundle_path)
    config_file = os.path.join(bundle_path, manifest["files"]["config"])
    config.from_file(config_file)

    ctx = wise.AnalysisContext(config)
    wise.tasks.load(ctx, name)

    return ctx
