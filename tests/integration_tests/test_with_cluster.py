import os
from time import sleep
import requests
from subprocess import run

from kubernetes import client

from automl.defaults import AUTOML_NAMESPACE
from automl.k8s.logs import get_runner_logs


def test_successful_cli_workflow(
    load_balancer_ip_or_hostname
):
    process = run(
        [
            "automl",
            "create",
            "workflow",
            "example-workflow",
            "https://github.com/valeger/automl-example-project",
        ],
        encoding="utf-8",
        capture_output=True,
    )

    assert "Creating workflow=example-workflow" in process.stdout

    sleep(60)

    process = run(
        [
            "automl",
            "get",
            "workflow",
            "example-workflow",
            "--logs"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    expected_log_1 = (
        "Jobs at stage=train in example-workflow "
        "workflow were successfully completed"
    )
    expected_log_2 = (
        "Jobs at stage=compare in example-workflow "
        "workflow were successfully completed"
    )
    expected_log_3 = (
        "Rolling update of deployments at stage serve in "
        "example-workflow workflow was successfully performed"
    )
    assert expected_log_1 in process.stdout
    assert expected_log_2 in process.stdout
    assert expected_log_3 in process.stdout

    deployment_objects = client.AppsV1Api().list_namespaced_deployment(
        namespace=AUTOML_NAMESPACE
    ).items
    job_objects = client.BatchV1Api().list_namespaced_job(
        namespace=AUTOML_NAMESPACE
    ).items
    service_objects = client.CoreV1Api().list_namespaced_service(
        namespace=AUTOML_NAMESPACE
    ).items
    ingress_objects = client.NetworkingV1Api().list_namespaced_ingress(
        namespace=AUTOML_NAMESPACE
    ).items
    secret_objects = client.CoreV1Api().list_namespaced_secret(
        namespace=AUTOML_NAMESPACE,
        label_selector="app=automl"
    ).items

    assert len(job_objects) == 5
    assert len(deployment_objects) == 2
    assert len(service_objects) == 2
    assert len(ingress_objects) == 1
    assert len(secret_objects) == 1

    process = run(
        [
            "automl",
            "update",
            "workflow",
            "example-workflow",
            "https://github.com/valeger/automl-example-project",
            "--branch",
            "new-feature"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        "Updating the runner in example-workflow "
        f"workflow within {AUTOML_NAMESPACE} namespace"
    ) in process.stdout

    sleep(80)

    deployment_objects = client.AppsV1Api().list_namespaced_deployment(
        namespace=AUTOML_NAMESPACE
    ).items
    job_objects = client.BatchV1Api().list_namespaced_job(
        namespace=AUTOML_NAMESPACE
    ).items
    service_objects = client.CoreV1Api().list_namespaced_service(
        namespace=AUTOML_NAMESPACE
    ).items
    ingress_objects = client.NetworkingV1Api().list_namespaced_ingress(
        namespace=AUTOML_NAMESPACE
    ).items
    secret_objects = client.CoreV1Api().list_namespaced_secret(
        namespace=AUTOML_NAMESPACE,
        label_selector="app=automl"
    ).items

    print(get_runner_logs(workflow_name="example-workflow", namespace="automl"))
    assert len(job_objects) == 6
    assert len(deployment_objects) == 1
    assert len(service_objects) == 1
    assert len(ingress_objects) == 1
    assert len(secret_objects) == 1

    ingress_object = client.NetworkingV1Api().list_namespaced_ingress(
        namespace=AUTOML_NAMESPACE,
        label_selector=(
            "app=automl,workflow={0},stage={1},step={2}".format(
                "example-workflow", "serve", "serve-model-1"
            )
        )
    ).items[0]

    ingress_path = ingress_object.spec.rules[0].http.paths[0].path

    response = requests.get(
        f"http://{load_balancer_ip_or_hostname}/{ingress_path}"
    )
    assert response.ok
    assert "Hello world" in response.text

    process = run(
        [
            "automl",
            "delete",
            "workflow",
            "example-workflow",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        f"Workflow=example-workflow in {AUTOML_NAMESPACE} namespace was deleted"
    ) in process.stdout

    sleep(20)

    process = run(
        [
            "automl",
            "get",
            "workflow",
            "example-workflow",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        f"No specified workflow=example-workflow exists in {AUTOML_NAMESPACE} namespace"
    ) in process.stdout


def test_cli_workflow_with_config_errors():
    process = run(
        [
            "automl",
            "create",
            "workflow",
            "example-workflow",
            "git@github.com/valeger/automl-example-project",
            "--check",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        "Error in git connection protocol: only https protocol is supported"
    ) in process.stdout

    process = run(
        [
            "automl",
            "create",
            "workflow",
            "example-workflow",
            "https://github.com/valeger/automl-example-project",
            "--check",
            "--branch",
            "config-error"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        "Cannot connect to docker repository: "
        "https://hub.docker.com/v2/repositories/foo/bar/tags/latest (code 404)"
    ) in process.stdout


def test_cli_workflow_with_job_error():
    process = run(
        [
            "automl",
            "create",
            "workflow",
            "example-workflow",
            "https://github.com/valeger/automl-example-project",
            "--branch",
            "job-error"
        ],
        encoding="utf-8",
    )

    sleep(40)

    process = run(
        [
            "automl",
            "get",
            "workflow",
            "example-workflow",
            "--logs"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        "Jobs during stage=train in "
        "example-workflow workflow failed to complete."
    ) in process.stdout

    process = run(
        [
            "automl",
            "delete",
            "workflow",
            "example-workflow"
        ],
        encoding="utf-8",
    )

    deployment_objects = client.AppsV1Api().list_namespaced_deployment(
        namespace=AUTOML_NAMESPACE
    ).items
    job_objects = client.BatchV1Api().list_namespaced_job(
        namespace=AUTOML_NAMESPACE
    ).items
    service_objects = client.CoreV1Api().list_namespaced_service(
        namespace=AUTOML_NAMESPACE
    ).items
    ingress_objects = client.NetworkingV1Api().list_namespaced_ingress(
        namespace=AUTOML_NAMESPACE
    ).items

    assert len(job_objects) == 0
    assert len(deployment_objects) == 0
    assert len(service_objects) == 0
    assert len(ingress_objects) == 0


def test_cli_workflow_with_deploy_error():
    process = run(
        [
            "automl",
            "create",
            "workflow",
            "example-workflow",
            "https://github.com/valeger/automl-example-project",
            "--branch",
            "deploy-error"
        ],
        encoding="utf-8",
    )

    sleep(80)

    process = run(
        [
            "automl",
            "get",
            "workflow",
            "example-workflow",
            "--logs"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        "Cannot rollout deployment at stage=serve of "
        "example-workflow workflow in 30 seconds. \n"
    ) in process.stdout

    deployment_objects = client.AppsV1Api().list_namespaced_deployment(
        namespace=AUTOML_NAMESPACE
    ).items

    assert len(deployment_objects) == 0

    process = run(
        [
            "automl",
            "delete",
            "workflow",
            "example-workflow",
        ],
        encoding="utf-8",
    )

    job_objects = client.BatchV1Api().list_namespaced_job(
        namespace=AUTOML_NAMESPACE
    ).items

    assert len(job_objects) == 0


def test_cli_workflow_with_private_repo():
    process = run(
        [
            "automl",
            "create",
            "workflow",
            "example-workflow",
            "https://github.com/valeger/private-automl-example-project",
            "--check"
        ],
        encoding="utf-8",
        capture_output=True,
    )

    expected_error_output = (
        "Cannot fetch configuration file from "
        "https://raw.githubusercontent.com/valeger/private-automl-example-project/master/config.yaml. "
        "Make sure you provide PAT token in case your repo is private."
    )
    assert expected_error_output in process.stdout

    process = run(
        [
            "automl",
            "create",
            "workflow",
            "example-workflow",
            "https://github.com/valeger/private-automl-example-project",
            "--token",
            f"{os.getenv('GITHUB_ACCESS_TOKEN')}"
        ],
        encoding="utf-8",
    )

    sleep(60)

    deployment_objects = client.AppsV1Api().list_namespaced_deployment(
        namespace=AUTOML_NAMESPACE
    ).items
    job_objects = client.BatchV1Api().list_namespaced_job(
        namespace=AUTOML_NAMESPACE
    ).items
    service_objects = client.CoreV1Api().list_namespaced_service(
        namespace=AUTOML_NAMESPACE
    ).items

    assert len(job_objects) == 2
    assert len(deployment_objects) == 1
    assert len(service_objects) == 1


def test_cli_workflow_with_secrets():
    process = run(
        [
            "automl",
            "create",
            "secret",
            "aws",
            "AWS_ACCESS_KEY_ID=123456",
            "AWS_SECRET_ACCESS_KEY=123456",
            "-w",
            "with-secrets",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert f"Secret aws was created in {AUTOML_NAMESPACE} namespace" in process.stdout

    process = run(
        ["automl", "get", "secrets"],
        encoding="utf-8",
        capture_output=True,
    )
    assert "aws" in process.stdout

    process = run(
        [
            "automl",
            "create",
            "workflow",
            "with-secrets",
            "https://github.com/valeger/automl-example-project",
            "--branch",
            "with-secrets",
        ],
        encoding="utf-8",
    )

    sleep(30)

    process = run(
        [
            "automl",
            "get",
            "workflow",
            "with-secrets",
            "--logs"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    expected_log = (
        "Jobs at stage=train in with-secrets "
        "workflow were successfully completed"
    )
    assert expected_log in process.stdout

    process = run(
        ["automl", "delete", "secret", "aws"],
    )

    process = run(
        [
            "automl",
            "update",
            "workflow",
            "with-secrets",
            "https://github.com/valeger/automl-example-project",
            "--branch",
            "with-secrets"
        ],
        encoding="utf-8",
    )

    sleep(30)

    process = run(
        [
            "automl",
            "get",
            "workflow",
            "with-secrets",
            "--logs"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    expected_log = (
        "aws secret(-s) was/were "
        f"not found in {AUTOML_NAMESPACE} namespace"
    )
    assert expected_log in process.stdout


def test_cli_cronworkflow():
    process = run(
        [
            "automl",
            "create",
            "cronworkflow",
            "example-cronworkflow",
            "https://github.com/valeger/automl-example-project",
            "--schedule=*/1 * * * *"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        f"Creating cronworkflow=example-cronworkflow in {AUTOML_NAMESPACE} namespace"
    ) in process.stdout

    process = run(
        [
            "automl",
            "get",
            "cronworkflow",
            "example-cronworkflow"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert "Requested resources are not found yet" in process.stdout

    assert client.BatchV1Api().list_namespaced_cron_job(
        AUTOML_NAMESPACE,
        label_selector=(
            "app=automl,workflow=example-cronworkflow,kind=runner"
        )
    ).items[0].spec.schedule == "*/1 * * * *"

    process = run(
        [
            "automl",
            "update",
            "cronworkflow",
            "example-cronworkflow",
            "https://github.com/valeger/automl-example-project",
            "--branch=new-feature",
            "--schedule=*/2 * * * *",
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        f"Updating cronworkflow=example-cronworkflow in {AUTOML_NAMESPACE} namespace"
    ) in process.stdout

    assert client.BatchV1Api().list_namespaced_cron_job(
        AUTOML_NAMESPACE,
        label_selector=(
            "app=automl,workflow=example-cronworkflow,kind=runner"
        )
    ).items[0].spec.schedule == "*/2 * * * *"

    process = run(
        [
            "automl",
            "delete",
            "cronworkflow",
            "example-cronworkflow"
        ],
        encoding="utf-8",
        capture_output=True,
    )
    assert (
        f"Cronworkflow=example-cronworkflow in {AUTOML_NAMESPACE} namespace was deleted"
    ) in process.stdout
