import logging
import click

from automl.executions.client_execution import (
    delete_resources,
    delete_workflow_secret
)
from automl.processing.utils import fix_k8s_name
from automl.exceptions import exception_handler
from automl.defaults import AUTOML_NAMESPACE

from .utils import load_k8s_wrapper

logger = logging.getLogger("automl")


@click.command(
    name="secret",
    help="Delete secret."
)
@click.argument("name")
@click.option(
    "-n",
    "--namespace",
    type=click.STRING,
    default=AUTOML_NAMESPACE,
    help=(
        "Define namespace in which secrets will be deleted."
    )
)
@exception_handler(logger=logger)
@load_k8s_wrapper
def delete_secret(name, namespace):
    namespace = fix_k8s_name(namespace)
    name = fix_k8s_name(name)
    delete_workflow_secret(namespace, name)


@click.command(
    name="workflow",
    help="Delete workflow."
)
@click.argument(
    "name",
    required=True,
)
@click.option(
    "-n",
    "--namespace",
    type=click.STRING,
    default=AUTOML_NAMESPACE,
    help=(
        "Define namespace within which specified workflow was executed."
    )
)
@exception_handler(logger=logger)
@load_k8s_wrapper
def delete_workflow(name, namespace):
    namespace = fix_k8s_name(namespace)
    name = fix_k8s_name(name) if name else None
    delete_resources(namespace, name, type_of_flow="Workflow")


@click.command(
    name="cronworkflow",
    help="Delete cronworkflow."
)
@click.argument(
    "name",
    required=True,
)
@click.option(
    "-n",
    "--namespace",
    type=click.STRING,
    default=AUTOML_NAMESPACE,
    help=(
        "Define namespace within which specified cronworkflow was executed."
    )
)
@exception_handler(logger=logger)
@load_k8s_wrapper
def delete_cronworkflow(name, namespace):
    namespace = fix_k8s_name(namespace)
    name = fix_k8s_name(name)
    delete_resources(namespace, name, type_of_flow="Cronworkflow")


def delete_cli_group():
    group = click.Group(
        name='delete',
        help=(
            "Delete secrets, workflows/cronworkflows with specified name."
        )
    )
    group.add_command(delete_secret)
    group.add_command(delete_workflow)
    group.add_command(delete_workflow, name="w")
    group.add_command(delete_cronworkflow)
    group.add_command(delete_cronworkflow, name="cw")
    return group


delete_cli = delete_cli_group()
