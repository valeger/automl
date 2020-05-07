import typing as t
import pytest

from kubernetes import client

from automl.k8s.utils import get_deployment_name
from automl.defaults import (
    CLIENT_DOCKER_IMAGE,
    DOCKER_IMAGE,
    CONTAINER_NAME,
    AUTOML_NAMESPACE
)

from automl.k8s.job import get_job_name
from automl.processing.config import Config


class Const(object):
    URL: str = "https://github.com/foo/bar"
    WORKFLOW_NAME: str = "workflow"
    NAMESPACE: str = AUTOML_NAMESPACE
    STAGE_NAME: str = "foo"
    STEP_NAME: str = "bar"
    REPLICAS: int = 2
    EXECUTABLE_MODULE: str = "foo.py"
    DEPENDENCY_PATH: str = "bat.txt"
    PROJECT_DIR: str = "bar"
    DOCKER_IMG: str = DOCKER_IMAGE
    CLIENT_DOCKER_IMG: str = CLIENT_DOCKER_IMAGE
    BACKOFF_LIMIT: int = 2
    BRANCH: str = "master"
    CPU: float = 0.5
    MEMORY: int = 250
    ARGS = (
        f"git clone $(echo $REPO_URL) && "
        f"cd {PROJECT_DIR} && "
        f"git checkout {BRANCH} && "
        f"python -m pip install -r {DEPENDENCY_PATH} && "
        f"python {EXECUTABLE_MODULE}"
    )


@pytest.fixture(scope="session")
def const():
    return Const


@pytest.fixture(scope="function")
def test_deployment_object(const):
    container_resources = client.V1ResourceRequirements(
        requests={"cpu": f"{const.CPU}", "memory": f"{const.MEMORY}M"}
    )
    container = client.V1Container(
        name=CONTAINER_NAME,
        image=const.CLIENT_DOCKER_IMG,
        image_pull_policy="Always",
        resources=container_resources,
        command=["/bin/sh", "-c"],
        args=["python", const.EXECUTABLE_MODULE],
    )

    spec = client.V1PodSpec(
        containers=[container],
        restart_policy="Always",
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(
            labels={
                "app": "automl",
                "workflow": const.WORKFLOW_NAME,
                "stage": const.STAGE_NAME,
                "step": const.STEP_NAME,
            }
        ),
        spec=spec,
    )

    deployment_spec = client.V1DeploymentSpec(
        replicas=const.REPLICAS,
        template=template,
        selector={
            "matchLabels": {
                "app": "automl",
                "workflow": const.WORKFLOW_NAME,
                "stage": const.STAGE_NAME,
                "step": const.STEP_NAME,
            },
        }
    )

    deployment_metadata = client.V1ObjectMeta(
        namespace=const.NAMESPACE,
        name=get_deployment_name(
            const.WORKFLOW_NAME, const.STAGE_NAME, const.STEP_NAME
        ),
        labels={
            "app": "automl",
            "workflow": const.WORKFLOW_NAME,
            "stage": const.STAGE_NAME,
            "step": const.STEP_NAME,
            "branch": const.BRANCH
        },
        annotations={
            "executable_module": const.EXECUTABLE_MODULE,
        },
    )
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=deployment_metadata,
        spec=deployment_spec
    )
    return deployment


@pytest.fixture(scope="function")
def test_job_object(const):
    container_resources = client.V1ResourceRequirements(
        requests={"cpu": f"{const.CPU}", "memory": f"{const.MEMORY}M"}
    )

    container = client.V1Container(
        name=CONTAINER_NAME,
        image=CLIENT_DOCKER_IMAGE,
        image_pull_policy="Always",
        resources=container_resources,
        command=["/bin/sh", "-c"],
        args=["python", const.EXECUTABLE_MODULE],
    )

    spec = client.V1PodSpec(
        containers=[container],
        restart_policy="Never",
    )

    template = client.V1PodTemplateSpec(spec=spec)

    job_spec = client.V1JobSpec(
        template=template,
        completions=1,
        backoff_limit=const.BACKOFF_LIMIT
    )

    job_metadata = client.V1ObjectMeta(
        namespace=AUTOML_NAMESPACE,
        name=get_job_name(
            const.WORKFLOW_NAME, const.STAGE_NAME, const.STEP_NAME
        ),
        labels={
            "app": "automl",
            "workflow": const.WORKFLOW_NAME,
            "stage": const.STAGE_NAME,
            "step": const.STEP_NAME,
        },
        annotations={
            "executable_module": const.EXECUTABLE_MODULE
        }
    )

    job_object = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=job_metadata,
        spec=job_spec
    )

    return job_object


@pytest.fixture(scope="function")
def test_stages() -> t.Dict:
    config = Config(**{
        "version": "1.1",
        "stages": {
            "stage-1": [
                {
                    "step_name": "step-1",
                    "path_to_executable": "foo/bar.py",
                    "dependency_path": "bar.txt",
                    "image": "python:latest",
                    "cpu_request": 0.5,
                    "memory_request": 500,
                    "replicas": 2,
                    "backoff_limit": 2,
                    "revision_history_limit": 2,
                    "min_ready_seconds": 10
                },
                {
                    "step_name": "step-2",
                    "path_to_executable": "foo/bar.py",
                    "dependency_path": "bar.txt",
                    "image": "python:latest",
                    "cpu_request": 0.5,
                    "memory_request": 500,
                    "replicas": 2,
                    "backoff_limit": 2,
                    "revision_history_limit": 2,
                    "service": {
                        "port": 5000,
                        "ingress": False
                    }
                }
            ]
        }
    })

    return config.stages
