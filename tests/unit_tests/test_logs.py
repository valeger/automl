import logging
from unittest.mock import patch

from kubernetes import client

from automl.k8s.logs import get_job_logs, get_deploy_logs, get_runner_logs
from automl.defaults import AUTOML_NAMESPACE


@patch("kubernetes.client.BatchV1Api")
def test_get_runner_logs(mock_k8s_batch, caplog):

    mock_k8s_batch().list_namespaced_job.return_value = client.V1JobList(items=[])

    get_runner_logs("example-workflow", AUTOML_NAMESPACE)

    assert (
        f"Cannot find example-workflow runner in {AUTOML_NAMESPACE} namespace and its logs"
    ) in caplog.text


@patch("kubernetes.client.CoreV1Api")
def test_get_job_logs(mock_k8d_core, caplog):

    mock_k8d_core().list_namespaced_pod.return_value = client.V1PodList(
        items=[
            client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name="foo-pod",
                    namespace=AUTOML_NAMESPACE
                )
            ),
        ]
    )
    get_job_logs("foo-job", AUTOML_NAMESPACE)
    mock_k8d_core().read_namespaced_pod_log.assert_called_once_with(
        namespace=AUTOML_NAMESPACE,
        name="foo-pod"
    )

    mock_k8d_core().list_namespaced_pod.return_value = client.V1PodList(
        items=[]
    )
    get_job_logs("foo-job", AUTOML_NAMESPACE)
    assert (
        f"Cannot find job=foo-job in {AUTOML_NAMESPACE} namespace and its logs"
    ) in caplog.text


@patch("kubernetes.client.CoreV1Api")
def test_get_deploy_logs(mock_k8d_core, test_deployment_object, caplog):
    caplog.set_level(logging.ERROR)
    mock_k8d_core().list_namespaced_pod.return_value = client.V1PodList(
        items=[
            client.V1Pod(
                metadata=client.V1ObjectMeta(
                    name="foo-pod",
                    namespace=AUTOML_NAMESPACE
                )
            ),
        ]
    )
    get_deploy_logs(test_deployment_object)
    mock_k8d_core().read_namespaced_pod_log.assert_called_once_with(
        namespace=AUTOML_NAMESPACE,
        name="foo-pod"
    )

    mock_k8d_core().list_namespaced_pod.return_value = client.V1PodList(
        items=[]
    )
    get_deploy_logs(test_deployment_object)
    assert (
        f"Cannot find {test_deployment_object.metadata.name} deployment in "
        f"{test_deployment_object.metadata.namespace} namespace and its logs"
    ) in caplog.text
