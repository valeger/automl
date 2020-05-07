import logging

from unittest.mock import patch

import automl.k8s.authorization as auth
from automl.defaults import (
    AUTOML_NAMESPACE,
    AUTOML_SERVICE_ACCOUNT,
    AUTOML_CLUSTER_ROLE,
    AUTOML_CLUSTER_ROLE_BINDING
)


@patch("automl.k8s.authorization.create_cluster_role_binding")
@patch("automl.k8s.authorization.cluster_role_binding_exists")
@patch("automl.k8s.authorization.cluster_role_exists")
@patch("automl.k8s.authorization.create_service_account")
@patch("automl.k8s.authorization.service_account_exists")
@patch("automl.k8s.authorization.create_namespace")
@patch("automl.k8s.authorization.namespace_exists")
def test_set_k8s_auth(
    mock_namespace_exists,
    mock_create_namespace,
    mock_service_account_exists,
    mock_create_service_account,
    mock_cluster_role_exists,
    mock_cluster_role_binding_exists,
    mock_create_cluster_role_binding,
    caplog
):
    caplog.set_level(logging.INFO, logger="automl")

    mock_namespace_exists.return_value = False
    mock_create_namespace.side_effect = None
    mock_service_account_exists.return_value = False
    mock_create_service_account.side_effect = None
    mock_cluster_role_exists.return_value = True
    mock_cluster_role_binding_exists.return_value = False
    mock_create_cluster_role_binding.side_effect = None

    auth.set_k8s_auth(AUTOML_NAMESPACE)

    assert f"Creating namespace {AUTOML_NAMESPACE}" in caplog.text
    assert "Creating service account={0} within namespace {1}".format(
        AUTOML_SERVICE_ACCOUNT, AUTOML_NAMESPACE
    ) in caplog.text
    assert (
        "Creating cluster role binding={0} to bind {1} cluster role "
        "with service account {2} within {3} namespace.".format(
            AUTOML_CLUSTER_ROLE_BINDING, AUTOML_CLUSTER_ROLE,
            AUTOML_SERVICE_ACCOUNT, AUTOML_NAMESPACE
        )
    ) in caplog.text
