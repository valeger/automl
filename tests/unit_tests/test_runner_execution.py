import pytest
from unittest.mock import patch

from kubernetes import client

from automl.exceptions import StopWorkflowExecution, AutomlTimeoutError
from automl.executions.runner_execution import (
    run,
    execute_job_steps,
    execute_service_steps
)


@patch("automl.executions.runner_execution.execute_service_steps")
@patch("automl.executions.runner_execution.execute_job_steps")
def test_run(
    mock_execute_job_steps,
    mock_execute_service_steps,
    test_stages,
    const
):
    run(
        const.BRANCH,
        const.PROJECT_DIR,
        const.NAMESPACE,
        const.WORKFLOW_NAME,
        test_stages
    )

    stage_name, steps = test_stages.popitem()

    mock_execute_job_steps.assert_called_once_with(
        const.BRANCH, const.PROJECT_DIR,
        const.WORKFLOW_NAME, const.NAMESPACE,
        stage_name, [steps[0]]
    )
    mock_execute_service_steps.assert_called_once_with(
        const.BRANCH, const.PROJECT_DIR,
        const.WORKFLOW_NAME, const.NAMESPACE,
        stage_name, [steps[1]]
    )


@patch("automl.executions.runner_execution.wait_for_jobs_complete")
@patch("automl.executions.runner_execution.create_job")
@patch("automl.executions.runner_execution.create_job_object")
@patch("automl.executions.runner_execution.delete_jobs")
def test_execute_job_steps_with_errors(
    mock_delete_jobs,
    mock_create_job_object,
    mock_create_job,
    mock_wait_for_jobs_complete,
    test_job_object,
    test_stages,
    const
):
    stage_name, steps = test_stages.popitem()

    mock_delete_jobs.side_effect = None
    mock_create_job_object.return_value = test_job_object
    mock_create_job.side_effect = None
    mock_wait_for_jobs_complete.side_effect = AutomlTimeoutError

    with pytest.raises(AutomlTimeoutError) as e:
        execute_job_steps(
            const.BRANCH, const.PROJECT_DIR,
            const.WORKFLOW_NAME, const.NAMESPACE,
            stage_name, [steps[0]]
        )
    assert (
        f"Jobs during stage={stage_name} in "
        f"{const.WORKFLOW_NAME} workflow failed to complete"
    ) in str(e.value)

    mock_wait_for_jobs_complete.side_effect = StopWorkflowExecution

    with pytest.raises(StopWorkflowExecution) as e:
        execute_job_steps(
            const.BRANCH, const.PROJECT_DIR,
            const.WORKFLOW_NAME, const.NAMESPACE,
            stage_name, [steps[0]]
        )
    assert (
        f"Jobs during stage={stage_name} in "
        f"{const.WORKFLOW_NAME} workflow failed to complete"
    ) in str(e.value)


@patch("automl.executions.runner_execution.delete_stale_deployment_resources")
@patch("automl.executions.runner_execution.create_service")
@patch("automl.executions.runner_execution.wait_for_deployment_complete")
@patch("automl.executions.runner_execution.create_deployment")
@patch("automl.executions.runner_execution.service_exists")
@patch("automl.executions.runner_execution.deployment_exists")
@patch("kubernetes.client.AppsV1Api")
@patch("kubernetes.client.CoreV1Api")
def test_execute_service_steps(
    mock_k8s_core,
    mock_k8s_api,
    mock_deploy_exists,
    mock_service_exists,
    mock_create_deploy,
    mock_wait_for_deploy_complete,
    mock_create_service,
    mock_delete_stale,
    test_stages,
    const
):
    stage_name, steps = test_stages.popitem()

    mock_k8s_core().list_namespaced_secret.return_value = client.V1SecretList(
        items=[
            client.V1Secret(
                metadata=client.V1ObjectMeta(
                    namespace=const.NAMESPACE,
                    name=f"repo-{const.WORKFLOW_NAME}"
                )
            )
        ]
    )
    mock_k8s_api().list_namespaced_deployment.return_value = client.V1DeploymentList(
        items=[]
    )
    mock_deploy_exists.return_value = False
    mock_service_exists.return_value = False
    mock_wait_for_deploy_complete.side_effect = None

    execute_service_steps(
        const.BRANCH, const.PROJECT_DIR,
        const.WORKFLOW_NAME, const.NAMESPACE,
        stage_name, [steps[1]]
    )

    mock_create_deploy.assert_called_once()
    mock_create_service.assert_called_once()
    mock_delete_stale.assert_called_once()


@patch("automl.executions.runner_execution.rollback_deployments")
@patch("automl.executions.runner_execution.wait_for_deployment_complete")
@patch("automl.executions.runner_execution.update_deployment")
@patch("automl.executions.runner_execution.deployment_exists")
@patch("kubernetes.client.AppsV1Api")
@patch("kubernetes.client.CoreV1Api")
def test_execute_service_steps_with_errors(
    mock_k8s_core,
    mock_k8s_api,
    mock_deploy_exists,
    mock_update_deploy,
    mock_wait_for_deploy_complete,
    mock_rollback,
    test_stages,
    const
):
    stage_name, steps = test_stages.popitem()

    mock_k8s_core().list_namespaced_secret.return_value = client.V1SecretList(
        items=[
            client.V1Secret(
                metadata=client.V1ObjectMeta(
                    namespace=const.NAMESPACE,
                    name=f"repo-{const.WORKFLOW_NAME}"
                )
            )
        ]
    )
    mock_k8s_api().list_namespaced_deployment.return_value = client.V1DeploymentList(
        items=[]
    )
    mock_deploy_exists.return_value = True
    mock_update_deploy.side_effect = None
    mock_wait_for_deploy_complete.side_effect = AutomlTimeoutError

    with pytest.raises(AutomlTimeoutError):
        execute_service_steps(
            const.BRANCH, const.PROJECT_DIR,
            const.WORKFLOW_NAME, const.NAMESPACE,
            stage_name, [steps[1]]
        )
    mock_rollback.assert_called_once()
