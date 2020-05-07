import logging

import pytest
from unittest.mock import patch
from kubernetes import client
from automl.exceptions import StopWorkflowExecution
from automl.executions.client_execution import (
    create_runner_object,
    create_workflow_runner,
    update_workflow_runner,
    delete_workflow_runner,
    runner_exists,
    create_workflow_secret,
    update_workflow_secret,
    delete_workflow_secret
)


@patch("automl.executions.client_execution.create_envs_from_secrets")
def test_create_runner_object(mock_envs_from, const):
    mock_envs_from.return_value = [
        client.V1EnvFromSource(
            secret_ref=client.V1SecretEnvSource(
                name="secret"
            )
        )
    ]

    runner_object = create_runner_object(
        const.WORKFLOW_NAME,
        const.NAMESPACE,
        const.URL,
        const.PROJECT_DIR,
        const.BRANCH
    )

    assert runner_object.metadata.namespace == const.NAMESPACE
    assert runner_object.metadata.labels["app"] == "automl"
    assert runner_object.metadata.labels["kind"] == "runner"
    assert runner_object.metadata.labels["workflow"] == const.WORKFLOW_NAME
    assert runner_object.metadata.annotations["url"] == const.URL

    assert runner_object.spec.template.spec.containers[0].image == const.DOCKER_IMG
    assert runner_object.spec.template.spec.containers[0].command == ["automl", "run"]
    assert runner_object.spec.template.spec.containers[0].args == [
        "--workflow", const.WORKFLOW_NAME,
        "--branch", const.BRANCH, "--project-dir",
        const.PROJECT_DIR, "--namespace", const.NAMESPACE
    ]
    assert (
        runner_object.spec.template.spec.containers[0].env_from[0].secret_ref.name
        == "secret"
    )


@patch("kubernetes.client.BatchV1Api")
@patch("automl.executions.client_execution.create_runner_object")
@patch("automl.executions.client_execution.runner_exists")
@patch("automl.executions.client_execution.cron_runner_exists")
def test_create_workflow_runner(
    mock_cron_exists, mock_runner_exists,
    mock_create, mock_k8s_batch, const
):
    mock_runner_exists.return_value = True
    with pytest.raises(StopWorkflowExecution) as test_error:
        create_workflow_runner(
            const.WORKFLOW_NAME, const.NAMESPACE,
            const.URL, const.PROJECT_DIR, const.BRANCH
        )
        test_error.value.code == 1

    mock_runner_exists.return_value = False
    mock_cron_exists.return_value = False
    mock_k8s_batch().create_namespaced_job.side_effect = None

    create_workflow_runner(
        const.WORKFLOW_NAME, const.NAMESPACE,
        const.URL, const.PROJECT_DIR, const.BRANCH
    )

    mock_create.assert_called_once()


@patch("kubernetes.client.BatchV1Api")
@patch("automl.executions.client_execution.delete_workflow_runner")
@patch("automl.executions.client_execution.create_runner_object")
@patch("automl.executions.client_execution.runner_exists")
def test_update_workflow_runner(
    mock_runner_exists, mock_create, mock_delete,
    mock_k8s_batch, const, caplog
):
    caplog.set_level(logging.INFO)

    mock_runner_exists.return_value = False
    with pytest.raises(StopWorkflowExecution) as test_error:
        update_workflow_runner(
            const.WORKFLOW_NAME, const.NAMESPACE,
            const.URL, const.PROJECT_DIR, const.BRANCH
        )
        test_error.value.code == 1

    mock_runner_exists.return_value = True
    mock_delete.side_effect = None

    test_job_object = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(
            name=const.WORKFLOW_NAME,
            namespace=const.NAMESPACE,
        )
    )

    mock_create.return_value = test_job_object

    update_workflow_runner(
        const.WORKFLOW_NAME, const.NAMESPACE,
        const.URL, const.PROJECT_DIR, const.BRANCH
    )
    mock_k8s_batch().create_namespaced_job.assert_called_once_with(
        body=test_job_object,
        namespace=test_job_object.metadata.namespace
    )
    assert (
        "Updating the runner in {0} workflow within {1} namespace".format(
            test_job_object.metadata.name,
            test_job_object.metadata.namespace
        ) in caplog.text
    )


@patch("kubernetes.client.BatchV1Api")
def test_delete_workflow_runner(mock_k8s_batch, const):
    mock_k8s_batch().list_namespaced_job.return_value = client.V1JobList(
        items=[
            client.V1Job(
                metadata=client.V1ObjectMeta(
                    name="foo",
                    namespace=const.NAMESPACE
                )
            ),
        ]
    )

    delete_workflow_runner(const.NAMESPACE)

    mock_k8s_batch().delete_namespaced_job.assert_called_once_with(
        name="foo",
        namespace=const.NAMESPACE,
        propagation_policy="Background"
    )


@patch("kubernetes.client.BatchV1Api")
def test_runner_exists(mock_k8s_batch, const):
    mock_k8s_batch().list_namespaced_job.return_value = client.V1JobList(
        items=[
            client.V1Job(
                metadata=client.V1ObjectMeta(
                    name="foo",
                    namespace=const.NAMESPACE
                )
            ),
            client.V1Job(
                metadata=client.V1ObjectMeta(
                    name="bar",
                    namespace=const.NAMESPACE
                )
            ),
        ]
    )
    assert runner_exists(const.WORKFLOW_NAME, const.NAMESPACE) is True

    mock_k8s_batch().list_namespaced_job.return_value = client.V1JobList(items=[])
    assert runner_exists(const.WORKFLOW_NAME, const.NAMESPACE) is False


@patch("automl.executions.client_execution.create_secret")
@patch("automl.executions.client_execution.secret_exists")
def test_create_workflow_secret(
    mock_secret_exists,
    mock_create_secret
):
    mock_secret_exists.return_value = True
    create_workflow_secret("foo", {"FOO": "bar"}, "automl")
    mock_create_secret.assert_not_called()

    mock_secret_exists.return_value = False
    create_workflow_secret("foo", {"FOO": "bar"}, "automl")
    mock_create_secret.assert_called_once()


@patch("automl.executions.client_execution.update_secret")
@patch("automl.executions.client_execution.secret_exists")
def test_update_workflow_secret(
    mock_secret_exists,
    mock_update_secret
):
    mock_secret_exists.return_value = False
    update_workflow_secret("foo", {"FOO": "bar"}, "automl")
    mock_update_secret.assert_not_called()

    mock_secret_exists.return_value = True
    update_workflow_secret("foo", {"FOO": "bar"}, "automl")
    mock_update_secret.assert_called_once()


@patch("automl.executions.client_execution.delete_secrets")
@patch("automl.executions.client_execution.secret_exists")
def test_delete_workflow_secret(
    mock_secret_exists,
    mock_delete_secrets
):
    mock_secret_exists.return_value = False
    delete_workflow_secret("automl", "foo")
    mock_delete_secrets.assert_not_called()

    mock_secret_exists.return_value = True
    delete_workflow_secret("automl", "foo")
    mock_delete_secrets.assert_called_once()
