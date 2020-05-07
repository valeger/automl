import logging
import click

from automl.k8s.logs import get_runner_logs
from automl.executions.client_execution import (
    tabulate_data,
    tabulate_secrets,
    tabulate_workflows,
    tabulate_cronworkflows,
    runner_exists,
    cron_runner_exists
)
from automl.processing.utils import fix_k8s_name
from automl.exceptions import exception_handler
from automl.defaults import AUTOML_NAMESPACE

from .utils import get_wrapper, load_k8s_wrapper

logger = logging.getLogger("automl")


@click.command(
    name="secrets",
    help="List all secrets in the tabular form."
)
@click.option(
    "-n",
    "--namespace",
    type=click.STRING,
    help="Namespace to search secrets in",
    default=AUTOML_NAMESPACE
)
@exception_handler(logger=logger)
@load_k8s_wrapper
def get_secrets(namespace):
    namespace = fix_k8s_name(namespace)
    to_print = tabulate_secrets(namespace)
    if to_print:
        print("\033[96m" + to_print + "\033[0m")


@click.command(
    name="workflows",
    help="List all workflows in the tabular form."
)
@click.option(
    "-n",
    "--namespace",
    type=click.STRING,
    help="Namespace to search name of workflows in",
    default=AUTOML_NAMESPACE
)
@exception_handler(logger=logger)
@load_k8s_wrapper
def get_workflows(namespace):
    namespace = fix_k8s_name(namespace)
    to_print = tabulate_workflows(namespace)
    if to_print:
        print("\033[96m" + to_print + "\033[0m")


@click.command(
    name="cronworkflows",
    help="List all scheduled workflows in the tabular form."
)
@click.option(
    "-n",
    "--namespace",
    type=click.STRING,
    help="Namespace to search name of cronworkflows in",
    default=AUTOML_NAMESPACE
)
@exception_handler(logger=logger)
@load_k8s_wrapper
def get_cronworkflows(namespace):
    namespace = fix_k8s_name(namespace)
    to_print = tabulate_cronworkflows(namespace)
    if to_print:
        print("\033[96m" + to_print + "\033[0m")


@click.command(
    name="workflow",
    help="List resources of the workflow in the tabular form."
)
@get_wrapper("workflow")
@exception_handler(logger=logger)
@load_k8s_wrapper
def get_workflow(name, namespace, logs):
    namespace = fix_k8s_name(namespace)
    name = fix_k8s_name(name)

    if not runner_exists(name, namespace):
        logger.warning(
            f"No specified workflow={name} exists in {namespace} namespace"
        )
        return

    if logs:
        logs = get_runner_logs(name, namespace)
        if logs:
            print(logs)

    else:
        to_print = tabulate_data(namespace, workflow_name=name)
        if to_print:
            print("\033[96m" + tabulate_data(namespace, workflow_name=name) + "\033[0m")


@click.command(
    name="cronworkflow",
    help="List resources of the cronworkflow in the tabular form."
)
@get_wrapper("cronworkflow")
@exception_handler(logger=logger)
@load_k8s_wrapper
def get_cronworkflow(name, namespace, logs):
    namespace = fix_k8s_name(namespace)
    name = fix_k8s_name(name)

    if not cron_runner_exists(name, namespace):
        logger.warning(
            f"No specified cronworkflow={name} exists in {namespace} namespace"
        )
        return

    if logs:
        logs = get_runner_logs(name, namespace, type_of_job="cronjob")
        if logs:
            print(logs)

    else:
        to_print = tabulate_data(namespace, workflow_name=name)
        if to_print:
            print("\033[96m" + tabulate_data(namespace, workflow_name=name) + "\033[0m")


def get_cli_group():
    group = click.Group(
        name="get",
        help=(
            "Describe in details all workflows, "
            "cronworkflows, theirs resources and secrets."
        )
    )
    group.add_command(get_secrets)
    group.add_command(get_workflow)
    group.add_command(get_workflow, name="w")
    group.add_command(get_workflows)
    group.add_command(get_workflows, name="ws")
    group.add_command(get_cronworkflow)
    group.add_command(get_cronworkflow, name="cw")
    group.add_command(get_cronworkflows)
    group.add_command(get_cronworkflows, name="cws")
    return group


get_cli = get_cli_group()
