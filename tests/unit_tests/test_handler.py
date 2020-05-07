import os
import logging
import urllib3
import requests
import pytest

from kubernetes import client

import automl.exceptions as e
from automl.k8s.authorization import load_kube_config

logger = logging.getLogger("root")


@pytest.mark.parametrize(
    "error,error_message,log_message",
    [
        (
            e.AutomlOSError,
            "Incorrect path in configuration file: /foo/bar. "
            "Files must have py or ipynb extensions",
            None
        ),
        (
            e.AutomlGitError,
            "Error in git connection protocol: "
            "only https protocol is supported.",
            None
        ),
        (
            e.AutomlValueError,
            "Incoreect schedule (cron) schema: * * *.",
            None
        ),
        (
            requests.HTTPError,
            "Cannot connect to docker repository:"
            " https://hub.docker.com/foo/bar",
            None
        ),
        (
            e.AutomlTimeoutError,
            "",
            None
        ),
        (
            e.StopWorkflowExecution,
            "The specified workflow=foo already exists in bar namespace",
            None
        ),
        (
            client.ApiException,
            {"status": 409, "reason": "Conflict"},
            "Kubernetes API error (code 409):"
        ),
        (
            IndexError,
            "list index out of range",
            "Unpredicted error has occured: list index out of range"
        ),
        (
            urllib3.exceptions.MaxRetryError,
            {"pool": "", "url": "/apis/apps/v1/namespaces/foo/deployments", "message": ""},
            "Cannot connect to Kubernetes API: /apis/apps/v1/namespaces/foo/deployments"
        )
    ]
)
def test_exception_handler(
    error,
    error_message,
    log_message,
    caplog
):
    caplog.set_level(logging.ERROR, logger="root")

    @e.exception_handler(logger=logger)
    def f():
        raise (
            error(error_message)
            if type(error_message) is str
            else error(**error_message)
        )
    f()
    assert log_message if log_message else error_message in caplog.text


def test_exception_handler_on_load_k8s(caplog):
    caplog.set_level(logging.ERROR, logger="root")

    os.environ["KUBERNETES_SERVICE_HOST"] = "bar"
    e.exception_handler(logger=logger)(lambda: load_kube_config())()
    assert "Cannot find credentials for authorization in a runner" in caplog.text
