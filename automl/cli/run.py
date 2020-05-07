import os
import logging
import click

from automl.executions.runner_execution import run
from automl.processing.utils import download_config
from automl.processing.config import create_and_validate_config
from automl.exceptions import exception_handler

from .utils import load_k8s_wrapper

logger = logging.getLogger("automl")


@click.command("run", hidden=True)
@click.option(
    "-w",
    "--workflow",
)
@click.option(
    "-b",
    "--branch",
)
@click.option(
    "--project-dir"
)
@click.option(
    "-n",
    "--namespace",
)
@exception_handler(logger=logger)
@load_k8s_wrapper
def run_cli(workflow, branch, project_dir, namespace):
    config_url = os.getenv("CONFIG_URL")
    unparsed_config = download_config(config_url)
    config = create_and_validate_config(unparsed_config)

    logger.info(
        f"Workflow={workflow} is started by runner"
    )

    run(
        branch=branch,
        project_dir=project_dir,
        namespace=namespace,
        workflow_name=workflow,
        stages=config.stages
    )
