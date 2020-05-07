import typing as t
from datetime import datetime
from time import sleep, time
from enum import Enum

from kubernetes import client

from automl.defaults import CLIENT_DOCKER_IMAGE, CONTAINER_NAME
from automl.exceptions import AutomlTimeoutError

from .service import service_exists
from .ingress import ingress_exists
from .utils import get_deployment_name
from .logs import get_deploy_logs
from .secret import (
    create_envs_from_secrets,
    get_repo_url_secret_name,
    get_docker_secret_name
)


class DeploymentStatus(Enum):
    AVAILABLE: str = "available"
    ROLLOUT: str = "rollout"


def create_deployment_object(
    branch: str,
    project_dir: str,
    workflow_name: str,
    namespace: str,
    stage_name: str,
    step_name: str,
    path_to_executable: str,
    dependency_path: str,
    image: str = CLIENT_DOCKER_IMAGE,
    command: t.List[str] = None,
    envs: t.Dict[str, str] = None,
    secrets: t.List[str] = [],
    cpu_request: float = None,
    memory_request: int = None,
    replicas: int = None,
    revision_history_limit: int = None,
    min_ready_seconds: int = None,
    **kwargs: t.Any
) -> client.V1Deployment:
    """Create a deployment object.

    :param branch: Branch of the remote git repo.
    :param project_dir: Project directory.
    :param workflow_name: The name of the current workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param stage_name: The name of the current stage.
    :param step_name: The name of the current step.
    :param path_to_executable: Path to .py or .ipynb module.
    :param dependency_path: Path to the requirements file.
    :param image: Client docker image repository.
                  If private repo provided, the secret of
                  type=kubernetes.io/dockerconfigjson
                  must be created in advance. Default repo is public.
    :param command: Client list of commands (== CMD command in Dockerfile).
    :param envs: Env variables to pass to container.
    :param secrets: Opaque kubernetes secrets to bind with container.
    :param cpu_request: Required amount of CPU resources per container (in cpu units).
    :param memory_request: Required amount of memory per container.
    :param replicas: Number of replicated Pods.
    :param revision_history_limit: Kubernetes .spec.revisionHistoryLimit param in
                                   Deployment spec.
    :param min_ready_seconds: Kubernetes .spec.minReadySeconds param in
                              Deployment spec.

    :return: Kubernetes V1Deployment object
    """
    container_resources = client.V1ResourceRequirements(
        requests={
            "cpu": f"{cpu_request}" if cpu_request else None,
            "memory": f"{memory_request}M" if memory_request else None,
        }
    )

    container_envs = [
        client.V1EnvVar(name=name, value=value)
        for name, value in envs.items()
    ] if envs else None

    envs_from = create_envs_from_secrets(
        secrets + [get_repo_url_secret_name(workflow_name)],
        namespace
    )

    if image == CLIENT_DOCKER_IMAGE:
        base_args = (
            "git clone $(echo $REPO_URL) && "
            f"cd {project_dir} && "
            f"git checkout {branch} && "
            f"python -m pip install -r {dependency_path} && "
        )

        custom_args = (
            " ".join(command)
            if command
            else f"python {path_to_executable}"
        )

        command = ["/bin/sh", "-c"]
        args = [base_args + custom_args]

    else:
        args = command
        command = None

    container = client.V1Container(
        name=CONTAINER_NAME,
        image=image,
        image_pull_policy="Always",
        resources=container_resources,
        env=container_envs,
        env_from=envs_from,
        command=command,
        args=args,
    )

    spec = client.V1PodSpec(
        containers=[container],
        restart_policy="Always",
        image_pull_secrets=[get_docker_secret_name(namespace)]
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(
            namespace=namespace,
            labels={
                "app": "automl",
                "workflow": workflow_name,
                "stage": stage_name,
                "step": step_name,
            },
        ),
        spec=spec,
    )

    deployment_spec = client.V1DeploymentSpec(
        replicas=replicas,
        template=template,
        selector={
            "matchLabels": {
                "app": "automl",
                "workflow": workflow_name,
                "stage": stage_name,
                "step": step_name,
            },
        },
        revision_history_limit=revision_history_limit,
        min_ready_seconds=min_ready_seconds
    )

    deployment_metadata = client.V1ObjectMeta(
        namespace=namespace,
        name=get_deployment_name(workflow_name, stage_name, step_name),
        labels={
            "app": "automl",
            "workflow": workflow_name,
            "stage": stage_name,
            "step": step_name,
            "branch": branch
        },
        annotations={
            "last-updated": datetime.now().isoformat(),
            "executable_module": path_to_executable,
        }
    )
    deployment = client.V1Deployment(
        api_version="apps/v1",
        kind="Deployment",
        metadata=deployment_metadata,
        spec=deployment_spec
    )
    return deployment


def create_deployment(deployment: client.V1Deployment) -> None:
    """Create a deployment in the k8s namespace.

    :param deployment: A configured deployment object.
    """
    client.AppsV1Api().create_namespaced_deployment(
        body=deployment, namespace=deployment.metadata.namespace
    )


def update_deployment(deployment: client.V1Deployment) -> None:
    """Update a deployment in the k8s namespace.

    :param deployment: A configured deployment object.
    """
    client.AppsV1Api().replace_namespaced_deployment(
        name=deployment.metadata.name,
        namespace=deployment.metadata.namespace,
        body=deployment
    )


def delete_deployments(
    namespace: str, workflow_name: str = None
) -> None:
    """Delete deployments.

    :param namespace: The name of the Kubernetes namespace.
    :param workflow_name: The name of the current workflow.
    """
    deployment_objects = client.AppsV1Api().list_namespaced_deployment(
        label_selector=(
            f"app=automl,workflow={workflow_name}"
            if workflow_name else "app=automl"
        ),
        namespace=namespace
    ).items

    for deployment_object in deployment_objects:
        client.AppsV1Api().delete_namespaced_deployment(
            name=deployment_object.metadata.name,
            namespace=namespace,
            propagation_policy="Background"
        )


def delete_stale_deployment_resources(
    previous_deployments: t.List[client.V1Deployment],
    current_deployments: t.List[client.V1Deployment],
) -> None:
    """Delete deployemnts, services and ingresses that are
    not specified anymore in the configuration file.

    :param previous_deployments: List of the previous deployment objects.
    :param current_deployments: List of the new configured deployment objects.
    """
    current_deployments_names = [
        current_deployment.metadata.name
        for current_deployment in current_deployments
    ]

    deployments_to_delete = [
        previous_deployment
        for previous_deployment in previous_deployments
        if previous_deployment.metadata.name
        not in current_deployments_names
    ]

    for deployment in deployments_to_delete:
        name = deployment.metadata.name
        namespace = deployment.metadata.namespace
        client.AppsV1Api().delete_namespaced_deployment(
            name=name,
            namespace=namespace
        )
        if service_exists(name, namespace):
            client.CoreV1Api().delete_namespaced_service(
                name=name,
                namespace=namespace
            )
        if ingress_exists(name, namespace):
            client.NetworkingV1Api().delete_namespaced_ingress(
                name=name,
                namespace=namespace
            )


def deployment_exists(deployment_name: str, namespace: str) -> bool:
    """Check if the specified deployment exists in the k8s namespace.

    :param deployment_name: The name of the deployment.
    :param namespace: The name of the Kubernetes namespace.

    :return: True if the deployemnt was found, otherwise False.
    """
    deployment_objects = client.AppsV1Api().list_namespaced_deployment(
        namespace=namespace
    ).items

    deployment_names = [
        deployment_object.metadata.name for deployment_object in deployment_objects
    ]

    return True if deployment_name in deployment_names else False


def get_deployment_status(deployment: client.V1Deployment) -> DeploymentStatus:
    """Get the latest status of a deployment created in the k8s namespace.

    :param deployment: A configured deployment object.

    :return: The current status of the deployment.
    """
    deployment_status = client.AppsV1Api().read_namespaced_deployment_status(
        name=deployment.metadata.name,
        namespace=deployment.metadata.namespace
    )

    if (
        deployment_status.status.available_replicas
        == deployment_status.status.replicas
    ):
        return DeploymentStatus.AVAILABLE
    elif (
        deployment_status.status.available_replicas is None or (
            deployment_status.status.replicas
            != deployment_status.status.available_replicas
        )
    ):
        return DeploymentStatus.ROLLOUT
    return None


def wait_for_deployment_complete(
    deployments: t.List[client.V1Deployment],
    timeout: int = 20,
    polling_time: int = 1,
    wait_before_start_time: int = 5,
) -> None:
    """Wait deployments to complete in timout seconds.

    :param deployments: The deployments to monitor.
    :param timeout: Max number of seconds to wait for deployments completion before
                    calling a custom timeout error. Defaults to 20.
    :param polling_time: Time between status polling (in seconds). Defaults to 1.
    :param wait_before_start_time: Time (in seconds) to wait before starting to monitor
                                   deployments (to allow deployments to be created,
                                   to install packages, etc).

    :raises automl.exceptions.AutomlTimeoutError: If the deployments failed to complete (i.e.
                                                  not available) in a fixed amount of time.
    """
    sleep(wait_before_start_time)
    start_time = time()
    deployments_status = [
        get_deployment_status(deployment) for deployment in deployments
    ]

    while DeploymentStatus.ROLLOUT in deployments_status:
        sleep(polling_time)
        if time() - start_time >= timeout:
            msg = "\n".join([
                f"\nDeployment={deployment.metadata.name}"
                f"\nLogs:\n{get_deploy_logs(deployment)}"
                for deployment, status in zip(deployments, deployments_status)
                if status == DeploymentStatus.ROLLOUT
            ])

            raise AutomlTimeoutError(msg)

        deployments_status = [
            get_deployment_status(deployment) for deployment in deployments
        ]


def rollback_deployments(
    previous_deployments: t.List[client.V1Deployment],
    current_deployments: t.List[client.V1Deployment]
) -> None:
    """Rollback deployments to the previous state.

    :param previous_deployments: List of the previous deployment objects.
    :param current_deployments: List of the new configured deployment objects.
    """
    deployments_to_rollback = dict([
        (previous.metadata.name, previous)
        for previous in previous_deployments
        for current in current_deployments
        if previous.metadata.name == current.metadata.name
    ])

    for deployment in current_deployments:
        name = deployment.metadata.name
        if name in deployments_to_rollback:
            body = deployments_to_rollback[f"{name}"]
            body.metadata.managed_fields = None
            body.metadata.uid = None
            body.metadata.resource_version = None
            body.metadata.creation_timestamp = None
            body.metadata.self_link = None
            client.AppsV1Api().replace_namespaced_deployment(
                name=name,
                namespace=deployment.metadata.namespace,
                body=body
            )
        else:
            client.AppsV1Api().delete_namespaced_deployment(
                name=name,
                namespace=deployment.metadata.namespace
            )


def list_deployments(
    namespace: str,
    workflow_name: str = None,
) -> t.List[t.Dict[str, t.Any]]:
    """List of the deployment info dictionaries within the specified workflow.

    :param namespace: The name of the Kubernetes namespace.
    :param workflow_name: The name of the current workflow.
    """
    deployments_objects = client.AppsV1Api().list_namespaced_deployment(
        label_selector=(
            f"app=automl,workflow={workflow_name}"
            if workflow_name else "app=automl"
        ),
        namespace=namespace
    ).items

    list_of_deployments = []
    for deployment_object in deployments_objects:
        info = {}
        info["namespace"] = deployment_object.metadata.namespace
        info["workflow"] = deployment_object.metadata.labels["workflow"]
        info["kind"] = "deployment"
        info["stage"] = deployment_object.metadata.labels["stage"]
        info["step"] = deployment_object.metadata.labels["step"]

        info["step_info"] = step_info = {}
        step_info["name"] = deployment_object.metadata.name
        step_info["last_updated"] = deployment_object.metadata.annotations["last-updated"]
        step_info["available_replicas"] = (
            deployment_object.status.available_replicas
            if deployment_object.status.available_replicas is not None
            else 0
        )
        step_info["required_replicas"] = deployment_object.status.replicas
        step_info["branch"] = deployment_object.metadata.labels["branch"]
        step_info["executable_module"] = (
            deployment_object.metadata.annotations["executable_module"]
        )
        pods = client.CoreV1Api().list_namespaced_pod(
            namespace=info["namespace"],
            label_selector=(
                "app=automl,workflow={0},stage={1},step={2}".format(
                    info["workflow"], info["stage"], info["step"]
                )
            )
        ).items
        step_info["pod_name"] = pods[0].metadata.name

        try:
            service_object = client.CoreV1Api().list_namespaced_service(
                namespace=info["namespace"],
                label_selector=(
                    "app=automl,workflow={0},stage={1},step={2}".format(
                        info["workflow"], info["stage"], info["step"]
                    )
                )
            ).items[0]

            step_info["servcie"] = service_object.metadata.name
            step_info["service_type"] = service_object.spec.type
            step_info["ports"] = [
                f"{port.port}:{port.node_port}/{port.protocol}"
                for port in service_object.spec.ports
            ]
        except IndexError:
            step_info["servcie"] = None

        try:
            ingress_object = client.NetworkingV1Api().list_namespaced_ingress(
                namespace=info["namespace"],
                label_selector=(
                    "app=automl,workflow={0},stage={1},step={2}".format(
                        info["workflow"], info["stage"], info["step"]
                    )
                )
            ).items[0]
            step_info["ingress_path"] = ingress_object.spec.rules[0].http.paths[0].path
            step_info["hostname"] = ingress_object.status.load_balancer.ingress[0].hostname
        except (IndexError, TypeError):
            step_info["ingress_path"] = None
            step_info["hostname"] = None

        list_of_deployments.append(info)

    return list_of_deployments
