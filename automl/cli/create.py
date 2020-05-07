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
    create_workflow_runner,
    create_cronworkflow_runner,
    create_workflow_secret,
    configure_repo_url_secret
)
from automl.k8s.authorization import set_k8s_auth
from automl.exceptions import exception_handler
from automl.defaults import AUTOML_NAMESPACE

from .utils import create_and_update_wrapper, load_k8s_wrapper

logger = logging.getLogger("automl")


@click.command(
    name="secret",
    help="Create secrets."
)
@click.argument("name")
@click.argument("data", nargs=-1)
@click.option(
    "-w",
    "--workflow",
    type=click.STRING,
    help=(
        "Define name of a workflow to bound secrets with"
    )
)
@click.option(
    "-n",
    "--namespace",
    type=click.STRING,
    help=(
        "Define namespace to put secrets in"
    ),
    default=AUTOML_NAMESPACE
)
@click.option(
    "-t",
    "--type",
    type=click.STRING,
    help=(
        """Type of the secret. Default to Opaque.
        See https://kubernetes.io/docs/concepts/configuration/secret/#secret-types.
        """
    ),
    default="Opaque"
)
@exception_handler(logger=logger)
@load_k8s_wrapper
def create_secret(name, data, workflow, namespace, type):
    name = fix_k8s_name(name)
    namespace = fix_k8s_name(namespace)
    workflow = fix_k8s_name(workflow) if workflow else None

    set_k8s_auth(namespace)

    create_workflow_secret(
        name,
        parse_secrets(data),
        namespace,
        workflow_name=workflow,
        type=type
    )


@click.command(
    name="workflow",
    help="Create workflow."
)
@create_and_update_wrapper("workflow")
@exception_handler(logger=logger)
@load_k8s_wrapper
def create_workflow(name, url, token, id, branch, namespace, file, check):
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

    create_workflow_runner(
        name,
        namespace,
        url,
        git_object.project,
        branch,
    )


@click.command(
    name="cronworkflow",
    help='Create scheduled workflow.'
)
@click.option(
    "-s",
    "--schedule",
    type=click.STRING,
    help=(
        "Provide schedule in the following format: "
        "`0 12 * * *`"
    ),
    required=True,
)
@create_and_update_wrapper("cronworkflow")
@exception_handler(logger=logger)
@load_k8s_wrapper
def create_cronworkflow(name, url, schedule, token, id, branch, namespace, file, check):
    name = fix_k8s_name(name)
    namespace = fix_k8s_name(namespace)
    schedule = validate_schedule(schedule)

    set_k8s_auth(namespace)

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

    create_cronworkflow_runner(
        schedule,
        name,
        namespace,
        url,
        git_object.project,
        branch,
    )


def create_cli_group():
    group = click.Group(
        name="create",
        help="Create workflow, cronworkflow or secrets."
    )
    group.add_command(create_secret)
    group.add_command(create_workflow)
    group.add_command(create_workflow, name="w")
    group.add_command(create_cronworkflow)
    group.add_command(create_cronworkflow, name="cw")
    return group


create_cli = create_cli_group()
