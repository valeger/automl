import os
import sys
import click
from logging.config import fileConfig

from automl.version import VERSION
from automl.defaults import ROOT_PACKAGE

from .create import create_cli
from .delete import delete_cli
from .get import get_cli
from .update import update_cli
from .run import run_cli


def create_automl_cli():
    commands = {
        "create": create_cli,
        "delete": delete_cli,
        "get": get_cli,
        "update": update_cli,
        "run": run_cli
    }

    @click.group(commands=commands)
    @click.version_option(
        version=VERSION,
        prog_name="automl"
    )
    def group():
        """CLI tools for working with automl."""

    # add the path for the cwd so imports in code work correctly
    sys.path.append(os.getcwd())
    return group


cli = create_automl_cli()


def main():
    fileConfig(ROOT_PACKAGE / "logger.conf", disable_existing_loggers=True)
    cli(obj={})


if __name__ == "__main__":
    main()
