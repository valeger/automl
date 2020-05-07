import typing as t
import logging

from kubernetes import client

logger = logging.getLogger("automl")


def get_runner_logs(
    workflow_name: str,
    namespace: str,
    type_of_job="job"
) -> t.Optional[str]:
    """Retrieve the logs from the a runner (a job) of the specified workflow.

    :param workflow_name: The name of the workflow the runner belongs to.
    :param namespace: The namespace in which the specified runner exists.
    :param type_of_job: Type of the runner.

    :return: The logs as a single string object.
    """
    try:
        if type_of_job == "job":
            job_name = client.BatchV1Api().list_namespaced_job(
                namespace=namespace,
                label_selector=(
                    "app=automl,kind=runner,"
                    f"workflow={workflow_name}"
                )
            ).items[0].metadata.name
        else:
            job_name = client.BatchV1Api().list_namespaced_cron_job(
                namespace=namespace,
                label_selector=(
                    "app=automl,kind=runner,"
                    f"workflow={workflow_name}"
                )
            ).items[0].metadata.name

    except IndexError:
        msg = f"Cannot find {workflow_name} runner in {namespace} namespace and its logs"
        logger.error(msg)
        return None

    pod_name = client.CoreV1Api().list_namespaced_pod(
        namespace=namespace,
        label_selector=(
            f"job-name={job_name}"
        )
    ).items[0].metadata.name

    pod_logs = client.CoreV1Api().read_namespaced_pod_log(
        namespace=namespace, name=pod_name
    )
    return t.cast(str, pod_logs[:-1]) if pod_logs else None


def get_job_logs(job_name: str, namespace: str) -> t.Optional[str]:
    """Retrieve the logs from the job.

    :param job_name: The name of the job to retrieve logs from.
    :param namespace: The namespace in which the specified job exists.

    :return: The logs as a single string object.
    """
    try:
        pod_name = client.CoreV1Api().list_namespaced_pod(
            namespace=namespace,
            label_selector=(
                f"job-name={job_name}"
            )
        ).items[0].metadata.name
    except IndexError:
        msg = f"Cannot find job={job_name} in {namespace} namespace and its logs"
        logger.error(msg)
        return None

    pod_logs = client.CoreV1Api().read_namespaced_pod_log(
        namespace=namespace, name=pod_name
    )
    return t.cast(str, pod_logs[:-1])


def get_deploy_logs(deployment_object: client.V1Deployment) -> t.Optional[str]:
    """Retrieve the logs from the pod of the specified deployment.

    :param deployment_object: The deployment object to retrieve logs from.

    :return: The logs as a single string object.
    """
    try:
        namespace = deployment_object.metadata.namespace
        step = deployment_object.metadata.labels["step"]
        stage = deployment_object.metadata.labels["stage"]
        workflow = deployment_object.metadata.labels["workflow"]
        pod_name = client.CoreV1Api().list_namespaced_pod(
            namespace=namespace,
            label_selector=(
                "app=automl,workflow={0},stage={1},step={2}".format(
                    workflow, stage, step
                )
            )
        ).items[0].metadata.name
    except IndexError:
        msg = (
            f"Cannot find {deployment_object.metadata.name} deployment in "
            f"{namespace} namespace and its logs"
        )
        logger.error(msg)
        return None

    pod_logs = client.CoreV1Api().read_namespaced_pod_log(
        namespace=namespace, name=pod_name
    )
    return t.cast(str, pod_logs[:-1])
