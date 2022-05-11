from kubernetes import client

import pytest
from unittest.mock import patch

from automl.defaults import AUTOML_NAMESPACE
from automl.exceptions import StopWorkflowExecution, AutomlTimeoutError
from automl.k8s.job import (
    JobStatus,
    get_job_name,
    create_job_object,
    create_job,
    delete_jobs,
    get_job_status,
    wait_for_jobs_complete
)


@patch("automl.k8s.job.get_docker_secret_name")
@patch("automl.k8s.job.create_envs_from_secrets")
def test_create_job_object(mock_envs_from, mock_docker_secret, const):
    mock_envs_from.return_value = [
        client.V1EnvFromSource(
            secret_ref=client.V1SecretEnvSource(
                name="secret"
            )
        )
    ]
    mock_docker_secret.return_value = None

    job_object = create_job_object(
        const.BRANCH,
        const.PROJECT_DIR,
        const.WORKFLOW_NAME,
        const.NAMESPACE,
        const.STAGE_NAME,
        const.STEP_NAME,
        const.EXECUTABLE_MODULE,
        const.DEPENDENCY_PATH,
        image=const.CLIENT_DOCKER_IMG,
        cpu_request=const.CPU,
        memory_request=const.MEMORY,
        backoff_limit=const.BACKOFF_LIMIT,
    )

    job_object.metadata.name = get_job_name(
        const.WORKFLOW_NAME, const.STAGE_NAME, const.STEP_NAME
    )

    assert job_object.metadata.namespace == const.NAMESPACE
    assert job_object.metadata.labels["app"] == "automl"
    assert job_object.metadata.labels["workflow"] == const.WORKFLOW_NAME
    assert job_object.metadata.labels["stage"] == const.STAGE_NAME
    assert job_object.metadata.labels["step"] == const.STEP_NAME
    assert job_object.metadata.annotations["executable_module"] == const.EXECUTABLE_MODULE
    assert job_object.spec.backoff_limit == const.BACKOFF_LIMIT
    assert job_object.spec.template.spec.containers[0].image == const.CLIENT_DOCKER_IMG
    assert job_object.spec.template.spec.containers[0].args == [const.ARGS]
    assert (
        job_object.spec.template.spec.containers[0].env_from[0].secret_ref.name
        == "secret"
    )
    assert (
        job_object.spec.template.spec.containers[0].resources.requests["cpu"]
        == f"{const.CPU}"
    )
    assert (
        job_object.spec.template.spec.containers[0].resources.requests["memory"]
        == f"{const.MEMORY}M"
    )


@patch("kubernetes.client.BatchV1Api")
def test_create_job(mock_k8s_batch, test_job_object):
    create_job(test_job_object)
    mock_k8s_batch().create_namespaced_job.assert_called_once_with(
        body=test_job_object,
        namespace=test_job_object.metadata.namespace
    )


@patch("kubernetes.client.BatchV1Api")
def test_delete_jobs(mock_k8s_batch):
    mock_k8s_batch().list_namespaced_job.return_value = client.V1JobList(
        items=[
            client.V1Job(
                metadata=client.V1ObjectMeta(
                    name="foo-job",
                    namespace=AUTOML_NAMESPACE
                )
            ),
        ]
    )

    delete_jobs(AUTOML_NAMESPACE)

    mock_k8s_batch().delete_namespaced_job.assert_called_once_with(
        name="foo-job",
        namespace=AUTOML_NAMESPACE,
        propagation_policy="Background"
    )


@patch("kubernetes.client.BatchV1Api")
def test_get_job_status(mock_k8s_batch, test_job_object):
    mock_k8s_batch().read_namespaced_job_status.return_value = test_job_object

    test_job_object.status = client.V1JobStatus(active=1)
    assert get_job_status(test_job_object) == JobStatus.ACTIVE

    test_job_object.status = client.V1JobStatus(succeeded=1)
    assert get_job_status(test_job_object) == JobStatus.SUCCEEDED

    test_job_object.status = client.V1JobStatus(failed=1)
    assert get_job_status(test_job_object) == JobStatus.FAILED

    test_job_object.status = client.V1JobStatus()
    with pytest.raises(RuntimeError):
        get_job_status(test_job_object)


@patch("automl.k8s.job.get_job_logs")
@patch("automl.k8s.job.get_job_status")
def test_wait_for_jobs_complete(
    mock_status, mock_logs, test_job_object
):
    mock_status.return_value = JobStatus.ACTIVE
    mock_logs.return_value = ""
    with pytest.raises(AutomlTimeoutError):
        wait_for_jobs_complete([test_job_object], timeout=5)

    mock_status.side_effect = [
        JobStatus.ACTIVE,
        JobStatus.ACTIVE,
        JobStatus.ACTIVE,
        JobStatus.SUCCEEDED
    ]
    wait_for_jobs_complete([test_job_object], timeout=5)

    mock_status.side_effect = [
        JobStatus.ACTIVE,
        JobStatus.ACTIVE,
        JobStatus.ACTIVE,
        JobStatus.FAILED
    ]
    with pytest.raises(StopWorkflowExecution):
        wait_for_jobs_complete([test_job_object], timeout=5)
