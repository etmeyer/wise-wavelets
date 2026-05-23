import glob
import logging
import os

from libwise import imgutils

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
        config.from_file(config_path)
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
    ext = '.set.dat'

    root = wise.find_project_root()
    if root is None:
        raise wise.ProjectRootNotFound(
            f"no project root found in {os.getcwd()}; run "
            f"`wise init` to create one, or cd into a directory "
            f"with a .wise/"
        )

    all_results_set = glob.glob(os.path.join(root, '*', '*' + ext))
    all_results_dirs = list(map(os.path.dirname, all_results_set))
    all_results_names = list(map(os.path.basename, all_results_dirs))

    if name not in all_results_names:
        return None

    idx = all_results_names.index(name)

    config_file = os.path.join(all_results_dirs[idx], '%s.config' % name)
    config.from_file(config_file)

    ctx = wise.AnalysisContext(config)
    wise.tasks.load(ctx, name)

    return ctx
