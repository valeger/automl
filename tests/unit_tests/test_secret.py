from datetime import datetime

from kubernetes import client

import pytest
from unittest.mock import patch
from automl.exceptions.automl_exceptions import StopWorkflowExecution

from automl.k8s.secret import (
    secret_exists,
    create_envs_from_secrets,
    get_docker_secret_name
)


@patch("kubernetes.client.CoreV1Api")
def test_secret_exists(mock_k8s_api):
    mock_k8s_api().list_namespaced_secret.return_value = client.V1SecretList(
        items=[
            client.V1Secret(
                metadata=client.V1ObjectMeta(
                    name="foo-secret",
                    namespace="automl"
                )
            ),
            client.V1Secret(
                metadata=client.V1ObjectMeta(
                    name="bar-secret",
                    namespace="automl"
                )
            ),
        ]
    )

    assert secret_exists("foo-secret", "automl") is True
    assert secret_exists("bar-secret", "automl") is True
    assert secret_exists("foo-bar-foo", "automl") is False


@patch("kubernetes.client.CoreV1Api")
def test_create_envs_from_secrets(mock_k8s_api):
    mock_k8s_api().list_namespaced_secret.return_value = client.V1SecretList(
        items=[
            client.V1Secret(
                metadata=client.V1ObjectMeta(
                    name="foo-secret",
                    namespace="automl"
                )
            ),
            client.V1Secret(
                metadata=client.V1ObjectMeta(
                    name="bar-secret",
                    namespace="automl"
                )
            ),
        ]
    )

    with pytest.raises(StopWorkflowExecution) as test_error:
        create_envs_from_secrets(["foo-secret", "bar"], "automl")
        test_error.value.code == 1


@patch("kubernetes.client.CoreV1Api")
def test_get_docker_secret_name(mock_k8s_api):
    mock_k8s_api().list_namespaced_secret.return_value = client.V1SecretList(
        items=[
            client.V1Secret(
                metadata=client.V1ObjectMeta(
                    name="foo-secret",
                    namespace="automl",
                    creation_timestamp=datetime(2020, 2, 13, hour=11)
                )
            ),
            client.V1Secret(
                metadata=client.V1ObjectMeta(
                    name="bar-secret",
                    namespace="automl",
                    creation_timestamp=datetime(2020, 2, 13, hour=12)
                )
            ),
        ]
    )

    assert get_docker_secret_name("automl").name == "bar-secret"
