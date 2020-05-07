import logging
import click

from automl.processing.git import GitURL
from automl.processing.utils import download_config, parse_secrets
from automl.processing.config import (
    create_and_validate_config,
    fix_k8s_name,
    validate_schedule
)
from automl.executions.client_execution import (
    update_workflow_runner,
    update_cronworkflow_runner,
    update_workflow_secret,
    configure_repo_url_secret
)
from automl.k8s.authorization import set_k8s_auth
from automl.exceptions import exception_handler
from automl.defaults import AUTOML_NAMESPACE

from .utils import create_and_update_wrapper, load_k8s_wrapper

logger = logging.getLogger("automl")


@click.command(
    name="secret",
    help="Update secret."
)
@click.argument("name")
@click.argument("data", nargs=-1)
@click.option(
    "-n",
    "--namespace",
    type=click.STRING,
    default=AUTOML_NAMESPACE
)
@exception_handler(logger=logger)
@load_k8s_wrapper
def update_secret(name, data, namespace):
    name = fix_k8s_name(name)
    namespace = fix_k8s_name(namespace)

    update_workflow_secret(
        name,
        parse_secrets(data),
        namespace
    )


@click.command(
    name="workflow",
    help="Update workflow."
)
@create_and_update_wrapper("workflow")
@exception_handler(logger=logger)
@load_k8s_wrapper
def update_workflow(name, url, token, id, branch, namespace, file, check):
    name = fix_k8s_name(name)
    namespace = fix_k8s_name(namespace)

    set_k8s_auth(namespace)

    git_object = GitURL(url, token=token, branch=branch, file=file, id=id)

    # check in advance
    if check:
        unparsed_config = download_config(git_object.raw_config_url)
        create_and_validate_config(unparsed_config)

    configure_repo_url_secret(
        namespace,
        name,
        git_object.repo_url,
        git_object.raw_config_url
    )

    update_workflow_runner(
        name,
        namespace,
        url,
        git_object.project,
        branch,
    )


@click.command(
    name="cronworkflow",
    help="Update cronworkflow."
)
@click.option(
    "-s",
    "--schedule",
    type=click.STRING,
    help=(
        "Provide schedule in folowwing format:"
        "`0 0 12 * *`"
    )
)
@create_and_update_wrapper("cronworkflow")
@exception_handler(logger=logger)
@load_k8s_wrapper
def update_cronworkflow(name, url, schedule, token, id, branch, namespace, file, check):
    name = fix_k8s_name(name)
    namespace = fix_k8s_name(namespace)

    set_k8s_auth(namespace)

    schedule = validate_schedule(schedule) if schedule else None

    git_object = GitURL(url, token=token, branch=branch, file=file, id=id)

    if check:
        unparsed_config = download_config(git_object.raw_config_url)
        create_and_validate_config(unparsed_config)

    configure_repo_url_secret(
        namespace,
        name,
        git_object.repo_url,
        git_object.raw_config_url
    )

    update_cronworkflow_runner(
        name,
        namespace,
        url,
        git_object.project,
        branch,
        schedule=schedule,
    )


def update_cli_group():
    group = click.Group(
        name="update",
        help="Update specified workflow/cronworkflow"
    )
    group.add_command(update_secret)
    group.add_command(update_workflow)
    group.add_command(update_workflow, name="w")
    group.add_command(update_cronworkflow)
    group.add_command(update_cronworkflow, name="cw")
    return group


update_cli = update_cli_group()
