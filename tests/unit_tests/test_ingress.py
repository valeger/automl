from kubernetes import client
from unittest.mock import patch

from automl.k8s.ingress import (
    create_ingress,
    delete_ingresses,
    create_ingress_object
)
from automl.k8s.deployment import get_deployment_name
from automl.defaults import AUTOML_NAMESPACE

WORKFLOW_NAME = "workflow"
STAGE_NAME = "stage"
STEP_NAME = "step"
PORT = 5000


@patch("kubernetes.client.NetworkingV1Api")
def test_create_ingress(mock_k8s_api):
    ingress_object = create_ingress_object(
        WORKFLOW_NAME, AUTOML_NAMESPACE, STAGE_NAME, STEP_NAME, PORT
    )

    assert ingress_object.metadata.name == get_deployment_name(
        WORKFLOW_NAME, STAGE_NAME, STEP_NAME
    )
    assert ingress_object.metadata.namespace == AUTOML_NAMESPACE
    assert ingress_object.metadata.labels["app"] == "automl"
    assert ingress_object.metadata.labels["workflow"] == WORKFLOW_NAME
    assert ingress_object.metadata.labels["stage"] == STAGE_NAME
    assert ingress_object.metadata.labels["step"] == STEP_NAME
    assert ingress_object.spec.rules[0].http.paths[0].path == "/{0}/{1}-{2}-{3}".format(
        AUTOML_NAMESPACE, WORKFLOW_NAME, STAGE_NAME, STEP_NAME
    )
    assert ingress_object.spec.rules[0].http.paths[0].backend.service.port.number == PORT

    create_ingress(ingress_object)
    mock_k8s_api().create_namespaced_ingress.assert_called_once_with(
        namespace=AUTOML_NAMESPACE,
        body=client.V1Ingress(
            api_version="networking.k8s.io/v1",
            kind="Ingress",
            metadata=ingress_object.metadata,
            spec=ingress_object.spec
        )
    )


@patch("kubernetes.client.NetworkingV1Api")
def test_delete_ingresses(mock_k8s_api):
    mock_k8s_api().list_namespaced_ingress.return_value = client.V1IngressList(
        items=[
            client.V1Ingress(
                metadata=client.V1ObjectMeta(
                    name="foo-ingress",
                    namespace=AUTOML_NAMESPACE
                )
            ),
        ]
    )

    delete_ingresses(AUTOML_NAMESPACE)

    mock_k8s_api().delete_namespaced_ingress.assert_called_once_with(
        name="foo-ingress",
        namespace=AUTOML_NAMESPACE,
        propagation_policy="Background"
    )


@patch("kubernetes.client.NetworkingV1Api")
def test_delete_zero_ingresses(mock_k8s_api):
    mock_k8s_api().list_namespaced_ingress.return_value = client.V1IngressList(
        items=[]
    )
    delete_ingresses(AUTOML_NAMESPACE)
    mock_k8s_api().delete_namespaced_ingress.assert_not_called()
