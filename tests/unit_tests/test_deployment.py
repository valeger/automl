from datetime import datetime
from copy import deepcopy

from kubernetes import client

import pytest
from unittest.mock import patch

from automl.defaults import AUTOML_NAMESPACE
from automl.k8s.utils import get_deployment_name
from automl.k8s.deployment import (
    create_deployment_object,
    create_deployment,
    delete_deployments,
    update_deployment,
    deployment_exists,
    delete_stale_deployment_resources,
    get_deployment_status,
    wait_for_deployment_complete,
    rollback_deployments,
    DeploymentStatus
)


@patch("automl.k8s.deployment.get_docker_secret_name")
@patch("automl.k8s.deployment.create_envs_from_secrets")
def test_create_object(mock_envs_from, mock_docker_secret, const):
    mock_envs_from.return_value = [
        client.V1EnvFromSource(
            secret_ref=client.V1SecretEnvSource(
                name="secret"
            )
        )
    ]
    mock_docker_secret.return_value = None

    deployment_object = create_deployment_object(
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
        replicas=const.REPLICAS
    )
    assert deployment_object.metadata.name == get_deployment_name(
        const.WORKFLOW_NAME, const.STAGE_NAME, const.STEP_NAME
    )
    assert deployment_object.metadata.namespace == const.NAMESPACE
    assert deployment_object.metadata.labels["app"] == "automl"
    assert deployment_object.metadata.labels["workflow"] == const.WORKFLOW_NAME
    assert deployment_object.metadata.labels["stage"] == const.STAGE_NAME
    assert deployment_object.metadata.labels["step"] == const.STEP_NAME
    assert deployment_object.metadata.labels["branch"] == const.BRANCH
    assert (
        deployment_object.metadata.annotations["executable_module"]
        == const.EXECUTABLE_MODULE
    )
    assert deployment_object.spec.replicas == const.REPLICAS
    assert (
        deployment_object.spec.template.spec.containers[0].image
        == const.CLIENT_DOCKER_IMG
    )
    assert deployment_object.spec.template.spec.containers[0].args == [const.ARGS]
    assert (
        deployment_object.spec.template.spec.containers[0].env_from[0].secret_ref.name
        == "secret"
    )
    assert (
        deployment_object.spec.template.spec.containers[0].resources.requests["cpu"]
        == f"{const.CPU}"
    )
    assert (
        deployment_object.spec.template.spec.containers[0].resources.requests["memory"]
        == f"{const.MEMORY}M"
    )


@patch("kubernetes.client.AppsV1Api")
def test_create_deployment(mock_k8s_api, test_deployment_object):
    create_deployment(test_deployment_object)
    mock_k8s_api().create_namespaced_deployment.assert_called_once_with(
        body=test_deployment_object,
        namespace=test_deployment_object.metadata.namespace
    )


@patch("kubernetes.client.AppsV1Api")
def test_update_deployment(mock_k8s_api, test_deployment_object, const):
    update_deployment(test_deployment_object)
    mock_k8s_api().replace_namespaced_deployment.assert_called_once_with(
        body=test_deployment_object,
        name=get_deployment_name(const.WORKFLOW_NAME, const.STAGE_NAME, const.STEP_NAME),
        namespace=AUTOML_NAMESPACE
    )


@patch("kubernetes.client.AppsV1Api")
def test_delete_deployments(mock_k8s_api):
    mock_k8s_api().list_namespaced_deployment.return_value = client.V1DeploymentList(
        items=[
            client.V1Deployment(
                metadata=client.V1ObjectMeta(
                    name="foo-deployment",
                    namespace=AUTOML_NAMESPACE
                )
            ),
        ]
    )

    delete_deployments(AUTOML_NAMESPACE)

    mock_k8s_api().delete_namespaced_deployment.assert_called_once_with(
        name="foo-deployment",
        namespace=AUTOML_NAMESPACE,
        propagation_policy="Background"
    )


@patch("kubernetes.client.AppsV1Api")
def test_deployment_exists(mock_k8s_api):
    mock_k8s_api().list_namespaced_deployment.return_value = client.V1DeploymentList(
        items=[
            client.V1Deployment(
                metadata=client.V1ObjectMeta(
                    name="foo-deployment",
                    namespace=AUTOML_NAMESPACE
                )
            ),
            client.V1Deployment(
                metadata=client.V1ObjectMeta(
                    name="bar-deployment",
                    namespace=AUTOML_NAMESPACE
                )
            ),
        ]
    )

    assert deployment_exists("foo-deployment", AUTOML_NAMESPACE) is True
    assert deployment_exists("bar-deployment", AUTOML_NAMESPACE) is True
    assert deployment_exists("zoo-deployment", AUTOML_NAMESPACE) is False


@patch("kubernetes.client.NetworkingV1Api")
@patch("kubernetes.client.CoreV1Api")
@patch("kubernetes.client.AppsV1Api")
@patch("automl.k8s.deployment.service_exists")
@patch("automl.k8s.deployment.ingress_exists")
def test_delete_stale_deployment_resources(
    mock_ingress_exists, mock_service_exists,
    mock_k8s_apps, mock_k8s_core, mock_k8s_network,
):
    previous_deployments = [
        client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name="foo-deployment",
                namespace=AUTOML_NAMESPACE
            )
        ),
        client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name="bar-deployment",
                namespace=AUTOML_NAMESPACE
            )
        ),
        client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name="baz-deployment",
                namespace=AUTOML_NAMESPACE
            )
        ),
    ]

    current_deployments = [
        client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name="bar-deployment",
                namespace=AUTOML_NAMESPACE
            )
        ),
        client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name="baz-deployment",
                namespace=AUTOML_NAMESPACE
            )
        ),
    ]

    mock_ingress_exists.return_value = False
    mock_service_exists.return_value = False

    delete_stale_deployment_resources(previous_deployments, current_deployments)

    mock_k8s_apps().delete_namespaced_deployment.assert_called_once_with(
        name="foo-deployment",
        namespace=AUTOML_NAMESPACE
    )
    mock_k8s_core().delete_namespaced_service.assert_not_called()
    mock_k8s_network().delete_namespaced_ingress.assert_not_called()

    mock_ingress_exists.return_value = True
    mock_service_exists.return_value = True

    delete_stale_deployment_resources(previous_deployments, current_deployments)

    mock_k8s_core().delete_namespaced_service.assert_called_once_with(
        name="foo-deployment",
        namespace=AUTOML_NAMESPACE
    )
    mock_k8s_network().delete_namespaced_ingress.assert_called_once_with(
        name="foo-deployment",
        namespace=AUTOML_NAMESPACE
    )


@patch("kubernetes.client.AppsV1Api")
def test_get_deployment_status(mock_k8s_api, test_deployment_object):
    def get_status(ready_replicas: int):
        return client.V1Job(
            metadata=client.V1ObjectMeta(
                name=test_deployment_object.metadata.name,
                namespace=test_deployment_object.metadata.namespace
            ),
            status=client.V1DeploymentStatus(
                replicas=test_deployment_object.spec.replicas,
                available_replicas=ready_replicas,
            )
        )

    mock_k8s_api().read_namespaced_deployment_status.side_effect = [
        get_status(test_deployment_object.spec.replicas),
        get_status(None)
    ]
    assert get_deployment_status(test_deployment_object) == DeploymentStatus.AVAILABLE
    assert get_deployment_status(test_deployment_object) == DeploymentStatus.ROLLOUT


@patch("automl.k8s.deployment.get_deploy_logs")
@patch("automl.k8s.deployment.get_deployment_status")
def test_wait_for_deployment_complete(
    mock_status, mock_logs, test_deployment_object
):
    mock_status.return_value = DeploymentStatus.ROLLOUT
    mock_logs.return_value = ""

    with pytest.raises(TimeoutError):
        wait_for_deployment_complete(
            [test_deployment_object], timeout=2,
            wait_before_start_time=1
        )
    mock_status.side_effect = [
        DeploymentStatus.ROLLOUT,
        DeploymentStatus.ROLLOUT,
        DeploymentStatus.ROLLOUT,
        DeploymentStatus.AVAILABLE,
    ]

    wait_for_deployment_complete(
        [test_deployment_object], timeout=5,
        wait_before_start_time=1
    )


@patch("kubernetes.client.AppsV1Api")
def test_rollback_deployments(
    mock_k8s_api,
    test_deployment_object
):
    current_deployments = [
        deepcopy(test_deployment_object),
        client.V1Deployment(
            metadata=client.V1ObjectMeta(
                name="test",
                namespace=test_deployment_object.metadata.namespace
            ),
        )
    ]
    current_deployments[0].metadata.annotations["last-updated"] = datetime.now().isoformat()

    rollback_deployments([test_deployment_object], current_deployments)

    mock_k8s_api().replace_namespaced_deployment.assert_called_once_with(
        name=test_deployment_object.metadata.name,
        namespace=test_deployment_object.metadata.namespace,
        body=test_deployment_object
    )
    mock_k8s_api().delete_namespaced_deployment.assert_called_once_with(
        name="test",
        namespace=test_deployment_object.metadata.namespace,
    )
