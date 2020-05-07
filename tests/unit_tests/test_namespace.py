from kubernetes import client
from unittest.mock import patch

from automl.k8s.namespace import (
    namespace_exists,
    create_namespace,
    delete_namespace
)


@patch("kubernetes.client.CoreV1Api")
def test_namespace_exists(mock_k8s_api):
    mock_k8s_api().list_namespace.return_value = client.V1NamespaceList(
        items=[
            client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name="automl"
                )
            ),
            client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name="foo-bar"
                )
            ),
        ]
    )

    assert namespace_exists("automl") is True
    assert namespace_exists("foo-bar") is True
    assert namespace_exists("foo-bar-foo") is False


@patch("kubernetes.client.CoreV1Api")
def test_create_namespace(mock_k8s_api):
    create_namespace("automl")

    mock_k8s_api().create_namespace.assert_called_once_with(
        body=client.V1Namespace(
            api_version="v1",
            kind="Namespace",
            metadata=client.V1ObjectMeta(
                name="automl"
            )
        )
    )


@patch("kubernetes.client.CoreV1Api")
def test_delete_namespace(mock_k8s_api):
    delete_namespace("automl")
    mock_k8s_api().delete_namespace.assert_called_once_with(
        name="automl",
        propagation_policy="Background"
    )
