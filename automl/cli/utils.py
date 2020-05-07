import typing as t
import functools

import click

from automl.k8s.authorization import load_kube_config
from automl.defaults import AUTOML_NAMESPACE


get_namespace_message = (
    "Define namespace within which specified {type_of_workflow} "
    "will be described in detail."
)


def apply_click_params(command, *click_params):
    for click_param in click_params:
        command = click_param(command)
    return command


def create_and_update_wrapper(type_of_flow):
    """Decorator for update and create CLI handlers"""
    def func_wrapper(f):
        return apply_click_params(
            f,
            click.argument(
                "url",
                type=click.STRING,
                required=True
            ),
            click.argument(
                "name",
                type=click.STRING,
                required=True
            ),
            click.option(
                "-t",
                "--token",
                type=click.STRING,
                help=(
                    "Specify PAT token for private repositories"
                )
            ),
            click.option(
                "--id",
                type=click.STRING,
                help=(
                    "Id of the gitlab private project"
                )
            ),
            click.option(
                "-b",
                "--branch",
                type=click.STRING,
                default="master",
                show_default=True,
                help=(
                    "Specify git branch"
                )
            ),
            click.option(
                "-n",
                "--namespace",
                type=click.STRING,
                help=(
                    "Define namespace within which specified "
                    f"{type_of_flow} will be executed"
                ),
                default=AUTOML_NAMESPACE
            ),
            click.option(
                "-f",
                "--file",
                type=click.STRING,
                help=(
                    "Specify configuration file in the root directory"
                ),
                default="config.yaml",
                show_default=True
            ),
            click.option(
                "--check",
                is_flag=True,
                help=(
                    "Check configuration file in advance before creating a runner"
                )
            )
        )

    return func_wrapper


def get_wrapper(type_of_workflow):
    """Decorator for get CLI handlers"""
    def wrapper(f):
        return apply_click_params(
            f,
            click.option(
                "--logs",
                help=(
                    "Show logs from all the pods (and runners) whithin the "
                    f"{type_of_workflow} (latest execution)."
                ),
                is_flag=True
            ),
            click.option(
                "-n",
                "--namespace",
                type=click.STRING,
                help=get_namespace_message.format(
                    type_of_workflow=type_of_workflow
                ),
                default=AUTOML_NAMESPACE
            ),
            click.argument(
                "name",
                required=True
            )
        )
    return wrapper


def load_k8s_wrapper(
    f: t.Callable[..., t.Any]
) -> t.Callable[..., t.Callable]:
    """Decorator for all CLI handlers to load a k8s cluster in advance."""
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        load_kube_config()
        f(*args, **kwargs)

    return wrapper
