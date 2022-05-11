import os
import typing as t
import logging

from tabulate import tabulate
from kubernetes import client

from automl.k8s.job import delete_jobs, list_jobs
from automl.k8s.service import delete_services
from automl.k8s.deployment import delete_deployments, list_deployments
from automl.k8s.ingress import delete_ingresses
from automl.k8s.secret import (
    create_secret,
    list_secrets,
    update_secret,
    secret_exists,
    delete_secrets,
    create_envs_from_secrets,
    get_repo_url_secret_name
)

from automl.exceptions import StopWorkflowExecution
from automl.defaults import (
    AUTOML_SERVICE_ACCOUNT,
    DOCKER_IMAGE,
    CONTAINER_NAME,
    RUNNER_TTL_AFTER_FINISHED,
    RUNNER_BACKOFF_LIMIT,
    RUNNER_SUCCESS_JOBS_LIMIT,
    RUNNER_FAILED_JOBS_LIMIT
)

logger = logging.getLogger("automl")


def create_runner_object(
    workflow_name: str,
    namespace: str,
    url: str,
    project_dir: str,
    branch: str,
    image: str = DOCKER_IMAGE,
    backoff_limit: int = RUNNER_BACKOFF_LIMIT,
    container_name=CONTAINER_NAME,
    service_account_name: str = AUTOML_SERVICE_ACCOUNT,
    ttl_seconds_after_finished: int = RUNNER_TTL_AFTER_FINISHED,
) -> client.V1Job:
    """Create a runner object (a job).

    :param workflow_name: The name of the current workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param url: Url of the remote git repo.
    :param project_dir: Project directory.
    :param branch: Branch of the remote git repo.
    :param image: Docker image repository (runner).
    :param backoff_limit: Kubernetes backoffLimit param in the job spec.
    :param container_name: Container name.
    :param service_account_name: Name of the service account
                                 to bind to the runner
    :param ttl_seconds_after_finished: Kubernetes spec.ttlSecondsAfterFinished
                                       param in the job spec

    :return: Kubernetes V1Job object.
    """

    docker_test_tag = os.getenv("DOCKER_TEST_TAG")
    container_envs = [
        client.V1EnvVar(name="DOCKER_TEST_TAG", value=docker_test_tag)
    ] if docker_test_tag else None

    container = client.V1Container(
        name=container_name,
        image=image,
        image_pull_policy="Always",
        env=container_envs,
        env_from=create_envs_from_secrets(
            [get_repo_url_secret_name(workflow_name)],
            namespace
        ),
        command=["automl", "run"],
        args=[
            "--workflow", workflow_name,
            "--branch", branch, "--project-dir",
            project_dir, "--namespace", namespace
        ]
    )

    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(
            namespace=namespace,
        ),
        spec=client.V1PodSpec(
            containers=[container],
            service_account_name=service_account_name,
            restart_policy="Never"
        ),
    )

    spec = client.V1JobSpec(
        template=template,
        backoff_limit=backoff_limit,
        ttl_seconds_after_finished=ttl_seconds_after_finished
    )

    runner = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            namespace=namespace,
            generate_name=f"{workflow_name}-",
            labels={
                "app": "automl",
                "kind": "runner",
                "workflow": workflow_name
            },
            annotations={
                "url": url
            }
        ),
        spec=spec
    )

    return runner


def create_workflow_runner(
    workflow_name: str,
    namespace: str,
    url: str,
    project_dir: str,
    branch: str
) -> None:
    """Create a runner on a kubernetes cluster.

    :param workflow_name: The name of the current workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param url: Url of the remote git repo.
    :param project_dir: Project directory.
    :param branch: Branch of the remote git repo.

    :raises automl.exceptions.StopWorkflowExecution: If the specified workflow already
                                                     exists in the defined namespace.
    """
    if (
        runner_exists(workflow_name, namespace)
        or cron_runner_exists(workflow_name, namespace)
    ):
        msg = "The specified workflow={0} already exists in {1} namespace".format(
            workflow_name, namespace
        )
        raise StopWorkflowExecution(msg)

    logger.info(f"Creating workflow={workflow_name} in {namespace} namespace")

    runner = create_runner_object(
        workflow_name,
        namespace,
        url,
        project_dir,
        branch
    )
    client.BatchV1Api().create_namespaced_job(
        body=runner,
        namespace=namespace
    )


def update_workflow_runner(
    workflow_name: str,
    namespace: str,
    url: str,
    project_dir: str,
    branch: str
) -> None:
    """Update the workflow runner on the kubernetes cluster.

    :param workflow_name: The name of the current workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param url: Url of the remote git repo.
    :param project_dir: Project directory.
    :param branch: Branch of the remote git repo.

    :raises automl.exceptions.StopWorkflowExecution: If the specified workflow does not
                                                     exist in the defined namespace.
    """
    if not runner_exists(workflow_name, namespace):
        msg = f"No specified workflow exists in {namespace} namespace."
        raise StopWorkflowExecution(msg)

    runner = create_runner_object(
        workflow_name,
        namespace,
        url,
        project_dir,
        branch
    )
    logger.info(
        "Updating the runner in {0} workflow within {1} namespace".format(
            workflow_name, namespace
        )
    )

    delete_workflow_runner(namespace, workflow_name=workflow_name)

    client.BatchV1Api().create_namespaced_job(
        body=runner,
        namespace=namespace,
    )


def create_cronworkflow_runner_object(
    schedule: str,
    workflow_name: str,
    namespace: str,
    url: str,
    project_dir: str,
    branch: str,
    successful_jobs_history_limit: int = RUNNER_SUCCESS_JOBS_LIMIT,
    failed_jobs_history_limit: int = RUNNER_FAILED_JOBS_LIMIT
) -> client.V1CronJob:
    """Create a scheduled runner object (a cronjob)

    :param schedule: Schedule of a cronjob.
                     Valid schedule expression: * * * * *
                     (minute, hour, day, month, year fields)
    :param workflow_name: The name of the scheduled workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param url: Url of the remote git repo.
    :param project_dir: Project directory.
    :param branch: Branch of the remote git repo.
    :param successful_jobs_history_limit: Kubernetes .spec.successfulJobsHistoryLimit
                                          param in the cronjob spec.
    :param failed_jobs_history_limit: Kubernetes .spec.failedJobsHistoryLimit param
                                      in the cronjob spec.

    :return: Kubernetes V1CronJob object.
    """
    runner = create_runner_object(
        workflow_name,
        namespace,
        url,
        project_dir,
        branch
    )

    template = client.V1JobTemplateSpec(
        metadata=runner.metadata,
        spec=runner.spec
    )

    spec = client.V1CronJobSpec(
        schedule=schedule,
        job_template=template,
        successful_jobs_history_limit=successful_jobs_history_limit,
        failed_jobs_history_limit=failed_jobs_history_limit,
    )

    cron_runner = client.V1CronJob(
        metadata=runner.metadata,
        spec=spec
    )

    return cron_runner


def create_cronworkflow_runner(
    schedule: str,
    workflow_name: str,
    namespace: str,
    url: str,
    project_dir: str,
    branch: str
) -> None:
    """Create a scheduled runner on a kubernetes cluster.

    :param schedule: Schedule of a cronjob.
                     Valid schedule expression: * * * * *
                     (minute, hour, day, month, year fields)
    :param workflow_name: The name of the scheduled workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param url: Url of the remote git repo.
    :param project_dir: Project directory.
    :param branch: Branch of the remote git repo.

    :raises automl.exceptions.StopWorkflowExecution: If the specified cronworkflow already
                                                     exists in the defined namespace.
    """
    if (
        runner_exists(workflow_name, namespace)
        or cron_runner_exists(workflow_name, namespace)
    ):
        msg = "The specified cronworkflow={0} already exists in {1} namespace".format(
            workflow_name, namespace
        )
        raise StopWorkflowExecution(msg)

    else:
        logger.info(f"Creating cronworkflow={workflow_name} in {namespace} namespace")

        cron_runner = create_cronworkflow_runner_object(
            schedule=schedule,
            workflow_name=workflow_name,
            namespace=namespace,
            url=url,
            project_dir=project_dir,
            branch=branch
        )

    client.BatchV1Api().create_namespaced_cron_job(
        body=cron_runner, namespace=cron_runner.metadata.namespace
    )


def update_cronworkflow_runner(
    workflow_name: str,
    namespace: str,
    url: str,
    project_dir: str,
    branch: str,
    schedule: str = None,
) -> None:
    """Update the scheduled runner on the kubernetes cluster.

    :param workflow_name: The name of the scheduled workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param url: Url of the remote git repo.
    :param project_dir: Project directory.
    :param branch: Branch of the remote git repo.
    :param schedule: Schedule of a cronjob.
                    Valid schedule expression: * * * * *
                    (minute, hour, day, month, year fields)
                    If None, the previous schedule will be used.
    :raises automl.exceptions.StopWorkflowExecution: If the specified cronworkflow does not
                                                     exist in the defined namespace.
    """
    if not cron_runner_exists(workflow_name, namespace):
        msg = f"No specified cronworkflow exists in {namespace} namespace."
        raise StopWorkflowExecution(msg)

    else:
        if schedule is None:
            schedule = client.BatchV1Api().list_namespaced_cron_job(
                namespace,
                label_selector=(
                    f"app=automl,workflow={workflow_name},kind=runner"
                )
            ).items[0].spec.schedule

        cron_runner = create_cronworkflow_runner_object(
            schedule,
            workflow_name,
            namespace,
            url,
            project_dir,
            branch
        )
        logger.info(
            "Updating cronworkflow={0} in {1} namespace".format(
                workflow_name, namespace
            )
        )
        delete_cronworkflow_runner(namespace, cronworkflow_name=workflow_name)

        client.BatchV1Api().create_namespaced_cron_job(
            body=cron_runner,
            namespace=namespace,
        )


def delete_workflow_runner(
    namespace: str,
    workflow_name: str = None
):
    """Delete one/all workflow runner/s within namespace.

    :param workflow_name: The name of the workflow.
    :param namespace: The name of the Kubernetes namespace.
    """
    runner_objects = client.BatchV1Api().list_namespaced_job(
        label_selector=(
            f"app=automl,workflow={workflow_name},kind=runner"
            if workflow_name else "app=automl,kind=runner"
        ),
        namespace=namespace
    ).items

    for runner_object in runner_objects:
        client.BatchV1Api().delete_namespaced_job(
            name=runner_object.metadata.name,
            namespace=namespace,
            propagation_policy="Background"
        )


def delete_cronworkflow_runner(
    namespace: str,
    cronworkflow_name: str = None
) -> None:
    """Delete one/all workflow runner/s within namespace.

    :param cronworkflow_name: The name of the scheduled workflow.
    :param namespace: The name of the Kubernetes namespace.
    """
    runner_objects = client.BatchV1Api().list_namespaced_cron_job(
        label_selector=(
            f"app=automl,workflow={cronworkflow_name},kind=runner"
            if cronworkflow_name else "app=automl,kind=runner"
        ),
        namespace=namespace
    ).items

    for runner_object in runner_objects:
        client.BatchV1Api().delete_namespaced_cron_job(
            name=runner_object.metadata.name,
            namespace=namespace,
            propagation_policy="Background"
        )


def runner_exists(workflow_name: str, namespace: str) -> bool:
    """Check if a workflow runner exists in the namespace.

    :param workflow_name: The name of the workflow.
    :param namespace: The name of the Kubernetes namespace.

    :return: True if the runner was found, otherwise False.
    """
    job_objects = client.BatchV1Api().list_namespaced_job(
        label_selector=(
            "app=automl,kind=runner,"
            f"workflow={workflow_name}"
        ),
        namespace=namespace
    ).items

    return True if len(job_objects) else False


def cron_runner_exists(workflow_name: str, namespace: str) -> bool:
    """Check if a cronworkflow runner exists in the namespace.

    :param workflow_name: The name of the scheduled workflow.
    :param namespace: The name of the Kubernetes namespace.

    :return: True if the runner was found, otherwise False.
    """
    cronjob_objects = client.BatchV1Api().list_namespaced_cron_job(
        label_selector=(
            "app=automl,kind=runner,"
            f"workflow={workflow_name}"
        ),
        namespace=namespace
    ).items

    return True if len(cronjob_objects) else False


def delete_resources(
    namespace: str,
    workflow_name: str,
    type_of_flow: str = None
):
    """Delete k8s resources of the specified workflow.

    :param workflow_name: The name of the workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param type_of_flow: Type of the workflow.
    """
    if type_of_flow == 'Workflow':
        delete_workflow_runner(namespace, workflow_name)
    else:
        delete_cronworkflow_runner(namespace, workflow_name)

    delete_jobs(namespace, workflow_name)
    delete_deployments(namespace, workflow_name)
    delete_services(namespace, workflow_name)
    delete_ingresses(namespace, workflow_name)
    delete_secrets(namespace, workflow_name)
    logger.info(f"{type_of_flow}={workflow_name} in {namespace} namespace was deleted")


def create_workflow_secret(
    name: str,
    data: t.Dict[str, str],
    namespace: str,
    workflow_name: str = None,
    type: str = "Opaque"
) -> None:
    """
    Create a secret if it does not exist in a kubernetes namespace.

    :param name:The name of the secret.
    :param data: Secret data provided in a Dict[str, str] format.
    :param namespace: The name of the Kubernetes namespace.
    :param workflow_name: The name of the workflow.
    :param type: Type of the secret.
                 See https://kubernetes.io/docs/concepts/configuration/secret/#secret-types
    """
    if secret_exists(name, namespace):
        logger.error(f"Secret {name} already exists in {namespace} namespace")
        return

    create_secret(name, data, namespace, workflow_name=workflow_name, type=type)
    logger.info(f"Secret {name} was created in {namespace} namespace")


def update_workflow_secret(
    name: str,
    data: t.Dict[str, str],
    namespace: str,
) -> None:
    """
    Update the secret if it does exist in the kubernetes namespace.

    :param name:The name of the secret.
    :param data: Updated secret data provided in a Dict[str, str] format.
    :param namespace: The name of the Kubernetes namespace.
    """
    if not secret_exists(name, namespace):
        logger.error(f"Secret {name} does not exist in {namespace} namespace")
        return

    update_secret(name, data, namespace)
    logger.info(f"Secret {name} was updated in {namespace} namespace")


def delete_workflow_secret(
    namespace: str,
    name: str
) -> None:
    """
    Delete the secret if it does exist in the kubernetes namespace.

    :param name: The name of the secret.
    :param namespace: The name of the Kubernetes namespace.
    """
    if secret_exists(name, namespace):
        delete_secrets(namespace, name=name)
        logger.info(f"Secret {name} was deleted in {namespace} namespace")
    else:
        logger.warning(f"Secret {name} not found in {namespace} namespace")


def configure_repo_url_secret(
    namespace: str,
    workflow_name: str,
    url: str,
    config_url: str
) -> None:
    """
    Create/update a repo-url secret to store sensitive PAT token data (if provided).

    :param namespace: The name of the Kubernetes namespace.
    :param workflow_name: The name of the workflow.
    :param url: Full url of the remote git repository with embedded PAT token.
    :param config_url: Full raw url to config.yaml file with embedded PAT token.
    """
    name = get_repo_url_secret_name(workflow_name)
    data = {"REPO_URL": url, "CONFIG_URL": config_url}

    if secret_exists(name, namespace):
        update_secret(name, data, namespace)
    else:
        create_secret(name, data, namespace, workflow_name=workflow_name)


def tabulate_secrets(namespace: str) -> t.Optional[str]:
    """
    Print secrets info in the tabular form.

    :param namespace: The name of the Kubernetes namespace.

    :return: Secrets info in the tabular form.
    """
    secrets = list_secrets(namespace)

    if not secrets:
        logger.warning(f"No secrets were found in {namespace} namespace")
        return None

    table = dict(
        name=[secret["name"] for secret in secrets],
        namespace=[secret["namespace"] for secret in secrets],
        workflow=[secret["workflow"] for secret in secrets],
        keys=["\n".join(secret["keys"]) for secret in secrets],
    )
    return tabulate(
        table,
        headers=["name of secret", "namespace", "name of cron-/workflow", "data keys"],
        tablefmt="fancy_grid"
    )


def tabulate_workflows(namespace: str) -> t.Optional[str]:
    """Print workflow names in the tabular form.

    :param namespace: The name of the Kubernetes namespace.

    :return: Workflows info in the tabular form.
    """
    runner_objects = client.BatchV1Api().list_namespaced_job(
        label_selector=(
            "app=automl,kind=runner"
        ),
        namespace=namespace
    ).items

    if not runner_objects:
        logger.warning(f"No workflows were found in {namespace} namespace")
        return None

    workflow_names = "\n".join([
        runner_object.metadata.labels["workflow"]
        for runner_object in runner_objects
    ])

    workflow_urls = "\n".join([
        runner_object.metadata.annotations["url"]
        for runner_object in runner_objects
    ])

    return tabulate(
        [[namespace, workflow_names, workflow_urls]],
        headers=["namespace", "name of workflow", "url"],
        tablefmt="fancy_grid"
    )


def tabulate_cronworkflows(namespace: str) -> t.Optional[str]:
    """Print cronworkflow names in the tabular form.

    :param namespace: The name of the Kubernetes namespace.

    :return: Cronworkflows info in the tabular form.
    """
    runner_objects = client.BatchV1Api().list_namespaced_cron_job(
        label_selector=(
            "app=automl,kind=runner"
        ),
        namespace=namespace
    ).items

    if not runner_objects:
        logger.warning(f"No cronworkflows were found in {namespace} namespace")
        return None

    cronworkflow_names = "\n".join([
        runner_object.metadata.labels["workflow"]
        for runner_object in runner_objects
    ])

    cronworkflow_urls = "\n".join([
        runner_object.metadata.annotations["url"]
        for runner_object in runner_objects
    ])

    schedules = "\n".join([
        runner_object.spec.schedule
        for runner_object in runner_objects
    ])

    return tabulate(
        [[namespace, cronworkflow_names, cronworkflow_urls, schedules]],
        headers=["namespace", "name of cronworkflow", "url", "schedule"],
        tablefmt="fancy_grid"
    )


def tabulate_data(namespace: str, workflow_name: str = None) -> t.Optional[str]:
    """Print workflow/cronworkflow resources info in the tabular form.

    :param namespace: The name of the Kubernetes namespace.
    :param workflow_name: The name of the workflow.

    :return: Resources info in the tabular form.
    """
    resources = (
        list_deployments(namespace, workflow_name=workflow_name)
        + list_jobs(namespace, workflow_name=workflow_name)
    )

    if not resources:
        logger.warning("Requested resources are not found yet")
        return None

    table = dict(
        namespace=[resource["namespace"] for resource in resources],
        workflow=[resource["workflow"] for resource in resources],
        kind=[resource["kind"] for resource in resources],
        stage=[resource["stage"] for resource in resources],
        step=[resource["step"] for resource in resources],
        key=[
            '\n'.join(str(k) for k in resource["step_info"].keys())
            for resource in resources
        ],
        value=[
            '\n'.join(str(v) for v in resource["step_info"].values())
            for resource in resources
        ],
    )
    return tabulate(table, headers="keys", tablefmt="fancy_grid")
