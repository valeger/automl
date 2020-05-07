import typing as t
import logging

from kubernetes import client
from automl.processing.config import StepConfig
from automl.k8s.job import (
    create_job,
    create_job_object,
    wait_for_jobs_complete,
    delete_jobs
)
from automl.k8s.deployment import (
    create_deployment_object,
    deployment_exists,
    update_deployment,
    create_deployment,
    wait_for_deployment_complete,
    rollback_deployments,
    delete_stale_deployment_resources
)
from automl.k8s.service import (
    create_service_object,
    create_service,
    service_exists
)
from automl.k8s.ingress import (
    create_ingress_object,
    create_ingress
)
from automl.exceptions import (
    AutomlTimeoutError,
    StopWorkflowExecution
)

logger = logging.getLogger("automl")


def run(
    branch: str,
    project_dir: str,
    namespace: str,
    workflow_name: str,
    stages: t.Dict[str, t.List[StepConfig]]
) -> None:
    """Run all stages and theirs steps (invocation from a runner).

    :param branch: Branch of the remote git repo.
    :param project_dir: Project directory.
    :param namespace: The name of the Kubernetes namespace.
    :param workflow_name: The name of the current workflow.
    :param stages: Dictionary of the stage names and step configurations.
    """
    for stage_name, stage_config in stages.items():
        job_configs = [
            config for config in stage_config
            if not config.service
        ]
        service_configs = [
            config for config in stage_config
            if config.service
        ]
        if job_configs:
            execute_job_steps(
                branch, project_dir, workflow_name,
                namespace, stage_name, job_configs
            )
        if service_configs:
            execute_service_steps(
                branch, project_dir, workflow_name,
                namespace, stage_name, service_configs
            )


def execute_job_steps(
    branch: str,
    project_dir: str,
    workflow_name: str,
    namespace: str,
    stage_name: str,
    step_configs: t.List[StepConfig],
) -> None:
    """Execute job steps within one stage (invocation from a runner).

    :param branch: Branch of the remote git repo.
    :param project_dir: Project directory.
    :param namespace: The name of the Kubernetes namespace.
    :param stage_name: The name of the current stage.
    :param step_configs: List of step configurations.

    :raises automl.exceptions.AutomlTimeoutError: If the jobs of the stage failed
                                                  to complete in a fixed amount of time
    :raises automl.exceptions.StopWorkflowExecution: If the errors occurred during
                                                     jobs execution.
    """
    delete_jobs(namespace, workflow_name, stage_name)

    job_objects = [
        create_job_object(
            branch, project_dir,
            workflow_name, namespace,
            stage_name, **step_config.dict()
        ) for step_config in step_configs
    ]
    for job_object in job_objects:
        create_job(job_object)

        logger.info(
            "Job {0} at step={1} during {2} stage was created".format(
                job_object.metadata.name,
                job_object.metadata.labels["step"],
                stage_name
            )
        )

    try:
        max_timeout = max(
            step_config.timeout for step_config in step_configs
        )
        wait_for_jobs_complete(
            job_objects, timeout=max_timeout
        )
    except AutomlTimeoutError as e:
        msg = (
            f"Jobs during stage={stage_name} in {workflow_name} workflow "
            f"failed to complete in {max_timeout} seconds."
            + str(e)
        )
        raise AutomlTimeoutError(msg) from e
    except StopWorkflowExecution as e:
        msg = (
            f"Jobs during stage={stage_name} in "
            f"{workflow_name} workflow failed to complete."
            + str(e)
        )
        raise StopWorkflowExecution(msg) from e
    logger.info(
        f"Jobs at stage={stage_name} in {workflow_name} "
        "workflow were successfully completed"
    )


def execute_service_steps(
    branch: str,
    project_dir: str,
    workflow_name: str,
    namespace: str,
    stage_name: str,
    step_configs: t.List[StepConfig],
):
    """Execute deployment steps within one stage (invocation from a runner).

    :param branch: Branch of the remote git repo.
    :param project_dir: Project directory.
    :param namespace: The name of the Kubernetes namespace.
    :param stage_name: The name of the current stage.
    :param step_configs: List of step configurations.

    :raises automl.exceptions.AutomlTimeoutError: If the deployments of the stage failed
                                                  to complete in a fixed amount of time
    """
    previous_deployments = client.AppsV1Api().list_namespaced_deployment(
        label_selector=(
            f"app=automl,workflow={workflow_name},stage={stage_name}"
        ),
        namespace=namespace
    ).items

    deployment_objects = [
        create_deployment_object(
            branch, project_dir,
            workflow_name, namespace,
            stage_name, **step_config.dict()
        ) for step_config in step_configs
    ]

    service_objects = [
        create_service_object(
            workflow_name, namespace,
            stage_name, step_config.step_name,
            **step_config.service.dict()
        ) for step_config in step_configs
    ]

    for deployment_object in deployment_objects:
        deployment_name = deployment_object.metadata.name
        if deployment_exists(deployment_name, namespace):
            update_deployment(deployment_object)

            logger.info(
                "Deployment {0} at step={1} during stage {2} was updated".format(
                    deployment_name, deployment_object.metadata.labels["step"],
                    stage_name
                )
            )
        else:
            create_deployment(deployment_object)

            logger.info(
                "Deployment {0} at step={1} during stage {2} was created".format(
                    deployment_name, deployment_object.metadata.labels["step"],
                    stage_name
                )
            )

    try:
        max_timeout = max(
            step_config.timeout for step_config in step_configs
        )
        wait_for_deployment_complete(
            deployment_objects,
            timeout=max_timeout
        )

    except AutomlTimeoutError as e:
        msg = (
            f"Cannot rollout deployment at stage={stage_name} of "
            f"{workflow_name} workflow in {max_timeout} seconds. \n"
            + str(e)
        )
        rollback_deployments(
            previous_deployments,
            deployment_objects
        )
        raise AutomlTimeoutError(msg) from e

    for service_object, step_config in zip(service_objects, step_configs):
        service_name = service_object.metadata.name

        if not service_exists(service_name, namespace):
            create_service(service_object)

            if step_config.service.ingress:
                ingree_object = create_ingress_object(
                    workflow_name, namespace,
                    stage_name, step_config.step_name,
                    **step_config.service.dict()
                )
                create_ingress(ingree_object)

    logger.info(
        f"Rolling update of deployments at stage {stage_name} in {workflow_name} "
        "workflow was successfully performed"
    )
    delete_stale_deployment_resources(
        previous_deployments,
        deployment_objects,
    )
