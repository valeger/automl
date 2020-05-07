from kubernetes import client
from unittest.mock import patch

from automl.k8s.service import (
    create_service,
    create_service_object,
    delete_services,
    service_exists
)
from automl.k8s.deployment import get_deployment_name
from automl.defaults import AUTOML_NAMESPACE

WORKFLOW_NAME = "workflow"
STAGE_NAME = "stage"
STEP_NAME = "step"
PORT = 5000


@patch("kubernetes.client.CoreV1Api")
def test_service_exists(mock_k8s_api):
    mock_k8s_api().list_namespaced_service.return_value = client.V1ServiceList(
        items=[
            client.V1Service(
                metadata=client.V1ObjectMeta(
                    name="foo-service",
                    namespace=AUTOML_NAMESPACE
                )
            ),
            client.V1Service(
                metadata=client.V1ObjectMeta(
                    name="bar-service",
                    namespace=AUTOML_NAMESPACE
                )
            ),
        ]
    )

    assert service_exists("foo-service", AUTOML_NAMESPACE) is True
    assert service_exists("bar-service", AUTOML_NAMESPACE) is True
    assert service_exists("foo-bar-foo", AUTOML_NAMESPACE) is False


@patch("kubernetes.client.CoreV1Api")
def test_create_service(mock_k8s_api):
    service_object = create_service_object(
        WORKFLOW_NAME, AUTOML_NAMESPACE,
        STAGE_NAME, STEP_NAME, PORT
    )
    assert service_object.metadata.name == get_deployment_name(
        WORKFLOW_NAME, STAGE_NAME, STEP_NAME
    )
    assert service_object.metadata.namespace == AUTOML_NAMESPACE
    assert service_object.metadata.labels["app"] == "automl"
    assert service_object.metadata.labels["workflow"] == WORKFLOW_NAME
    assert service_object.metadata.labels["stage"] == STAGE_NAME
    assert service_object.metadata.labels["step"] == STEP_NAME
    assert service_object.spec.type == "NodePort"
    assert service_object.spec.ports[0].port == PORT
    assert service_object.spec.selector["app"] == "automl"
    assert service_object.spec.selector["workflow"] == WORKFLOW_NAME
    assert service_object.spec.selector["stage"] == STAGE_NAME
    assert service_object.spec.selector["step"] == STEP_NAME

    create_service(service_object)
    mock_k8s_api().create_namespaced_service.assert_called_once_with(
        namespace=AUTOML_NAMESPACE,
        body=client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=service_object.metadata,
            spec=service_object.spec
        )
    )


@patch("kubernetes.client.CoreV1Api")
def test_delete_services(mock_k8s_api):
    mock_k8s_api().list_namespaced_service.return_value = client.V1ServiceList(
        items=[
            client.V1Service(
                metadata=client.V1ObjectMeta(
                    name="foo-service",
                    namespace=AUTOML_NAMESPACE
                )
            ),
        ]
    )

    delete_services(AUTOML_NAMESPACE)

    mock_k8s_api().delete_namespaced_service.assert_called_once_with(
        name="foo-service",
        namespace=AUTOML_NAMESPACE,
        propagation_policy="Background"
    )


@patch("kubernetes.client.CoreV1Api")
def test_delete_zero_services(mock_k8s_api):
    mock_k8s_api().list_namespaced_service.return_value = client.V1ServiceList(
        items=[]
    )
    delete_services(AUTOML_NAMESPACE)
    mock_k8s_api().delete_namespaced_ingress.assert_not_called()
