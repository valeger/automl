import typing as t
import uuid
from enum import Enum
from time import sleep, time

from kubernetes import client

from automl.exceptions import StopWorkflowExecution, AutomlTimeoutError
from automl.defaults import (
    CONTAINER_NAME,
    CLIENT_DOCKER_IMAGE,
)

from .logs import get_job_logs
from .secret import (
    create_envs_from_secrets,
    get_repo_url_secret_name,
    get_docker_secret_name
)


def get_job_name(
    workflow_name: str,
    stage_name: str,
    step_name: str
) -> str:
    return f"{workflow_name}-{stage_name}-{step_name}-{uuid.uuid4().hex[:6]}"


class JobStatus(Enum):
    """Possible states of a job."""

    ACTIVE: str = "active"
    SUCCEEDED: str = "succeeded"
    FAILED: str = "failed"


def create_job_object(
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
    backoff_limit: int = None,
    **kwargs: t.Any
) -> client.BatchV1Api:
    """Create a job object.

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
    :param backoff_limit: Kubernetes .spec.backoffLimit param in
                                   Job spec.

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
        restart_policy="Never",
        image_pull_secrets=[get_docker_secret_name(namespace)]
    )

    template = client.V1PodTemplateSpec(spec=spec)

    job_spec = client.V1JobSpec(
        template=template,
        completions=1,
        backoff_limit=backoff_limit
    )

    job_metadata = client.V1ObjectMeta(
        namespace=namespace,
        name=get_job_name(workflow_name, stage_name, step_name),
        labels={
            "app": "automl",
            "workflow": workflow_name,
            "stage": stage_name,
            "step": step_name,
        },
        annotations={
            "executable_module": path_to_executable
        }
    )

    job_object = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=job_metadata,
        spec=job_spec
    )

    return job_object


def create_job(job: client.V1Job) -> None:
    """Create a job in the k8s namespace.

    :param job: A configured job object.
    """
    client.BatchV1Api().create_namespaced_job(
        body=job,
        namespace=job.metadata.namespace
    )


def delete_jobs(namespace: str, workflow_name: str = None, stage_name: str = None) -> None:
    """Delete jobs in the k8s namespace.

    :param namespace: Namespace in which the jobs to delete exist.
    :param workflow_name: The name of the current workflow.
    :param stage_name: The name of the current stage.
    """
    if stage_name:
        label_selector = (
            f"app=automl,workflow={workflow_name},stage={stage_name}"
        )
    elif workflow_name:
        label_selector = f"app=automl,workflow={workflow_name}"
    else:
        label_selector = "app=automl"

    job_objects = client.BatchV1Api().list_namespaced_job(
        label_selector=label_selector,
        namespace=namespace
    ).items

    for job_object in job_objects:
        client.BatchV1Api().delete_namespaced_job(
            name=job_object.metadata.name,
            namespace=namespace,
            propagation_policy="Background",
        )


def get_job_status(job: client.V1Job) -> JobStatus:
    """Get the latest status of a job created in the k8s namespace.

    :param job: A configured job object.

    :return: The current status of the job.
    """
    job_object = client.BatchV1Api().read_namespaced_job_status(
        name=job.metadata.name,
        namespace=job.metadata.namespace,
    )
    if job_object.status.active is not None:
        return JobStatus.ACTIVE
    elif job_object.status.succeeded is not None:
        return JobStatus.SUCCEEDED
    elif job_object.status.failed is not None:
        return JobStatus.FAILED
    else:
        raise RuntimeError("Status of job is not found")


def wait_for_jobs_complete(
    job_objects: t.List[client.V1Job],
    timeout: int = 20,
    polling_time: int = 1,
    wait_before_start_time: int = 5,
) -> None:
    """Wait jobs to complete in timout seconds.

    :param jobs: The jobs to monitor.
    :param timeout: Max number of seconds to wait for jobs completion before
                    calling a custom timeout error. Defaults to 10.
    :param polling_time: Time between status polling (in seconds). Defaults to 20.
    :param wait_before_start_time: Time (in seconds) to wait before starting to monitor
                                   jobs (to allow jobs to be created,
                                   to install packages, etc).

    :raises automl.exceptions.AutomlTimeoutError: If the jobs failed to complete (i.e. are
                                                  still active) in a fixed amount of time.
    :raises automl.exceptions.StopWorkflowExecution: If the errors occurred during
                                                     jobs execution.
    """
    sleep(wait_before_start_time)
    start_time = time()
    jobs_status = [get_job_status(job_object) for job_object in job_objects]

    while JobStatus.ACTIVE in jobs_status:
        if timeout:
            if time() - start_time >= timeout:
                msg = "\n".join([
                    f"\nJob={job_object.metadata.name}"
                    "\nLogs:\n"
                    f"{get_job_logs(job_object.metadata.name,job_object.metadata.namespace)}"
                    for job_object, status in zip(job_objects, jobs_status)
                    if status != JobStatus.SUCCEEDED
                ])

                raise AutomlTimeoutError(msg)

        sleep(polling_time)

        jobs_status = [get_job_status(job_object) for job_object in job_objects]

    if JobStatus.FAILED in jobs_status:
        msg = "\n".join([
            f"\nJob={job_object.metadata.name}"
            "\nLogs:\n"
            f"{get_job_logs(job_object.metadata.name,job_object.metadata.namespace)}"
            for job_object, status in zip(job_objects, jobs_status)
            if status == JobStatus.FAILED
        ])
        raise StopWorkflowExecution(msg)


def list_jobs(
    namespace: str,
    workflow_name: str = None,
) -> t.List[t.Dict[str, t.Any]]:
    """List of the job info dictionaries within the specified workflow.

    :param namespace: The name of the Kubernetes namespace.
    :param workflow_name: The name of the current workflow.
    """
    job_objects = client.BatchV1Api().list_namespaced_job(
        label_selector=(
            f"app=automl,workflow={workflow_name}"
            if workflow_name else "app=automl"
        ),
        namespace=namespace
    ).items

    list_of_jobs = []
    for job_object in job_objects:
        info = {}
        if job_object.metadata.labels.get("kind"):
            continue
        info["namespace"] = namespace
        info["workflow"] = job_object.metadata.labels["workflow"]
        info["kind"] = "Job"
        info["stage"] = job_object.metadata.labels["stage"]
        info["step"] = job_object.metadata.labels["step"]

        info["step_info"] = step_info = {}  # type: ignore
        step_info["name"] = name = job_object.metadata.name
        step_info["start_time"] = job_object.status.start_time
        step_info["last_completion_time"] = job_object.status.completion_time
        step_info["executable_module"] = (
            job_object.metadata.annotations["executable_module"]
        )
        step_info["status"] = get_job_status(job_object).value
        step_info["pod_name"] = client.CoreV1Api().list_namespaced_pod(
            namespace=namespace,
            label_selector=(
                f"job-name={name}"
            )
        ).items[0].metadata.name
        list_of_jobs.append(info)

    return list_of_jobs
