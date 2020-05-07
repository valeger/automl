from click.testing import CliRunner
from unittest.mock import patch

from automl.cli.create import create_cli
from automl.cli.delete import delete_cli
from automl.cli.update import update_cli
from automl.cli.get import get_cli
from automl.cli.run import run_cli


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.create.create_workflow_secret")
@patch("automl.cli.create.set_k8s_auth")
def test_create_secret(
    mock_set_k8s,
    mock_create_secret,
    mock_load_k8s,
):
    mock_load_k8s.side_effect = None
    _ = CliRunner().invoke(
        create_cli,
        [
            "secret", "foo", "FOO=bar,BOO=baz",
            "--namespace", "namespace",
        ]
    )
    mock_set_k8s.assert_called_once()
    mock_create_secret.assert_called_once()


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.create.configure_repo_url_secret")
@patch("automl.cli.create.GitURL")
@patch("automl.cli.create.set_k8s_auth")
@patch("automl.cli.create.create_workflow_runner")
def test_create_workflow(
    mock_create_workflow,
    mock_set_k8s,
    mock_git,
    mock_configure_secret,
    mock_load_k8s,
):
    mock_load_k8s.side_effect = None
    _ = CliRunner().invoke(
        create_cli,
        [
            "workflow", "name", "url-repo",
            "--token", "token",
            "--branch", "master",
            "--namespace", "namespace",
            "--file", "config.yaml"
        ]
    )
    mock_set_k8s.assert_called_once()
    mock_git.assert_called_once()
    mock_configure_secret.assert_called_once()
    mock_create_workflow.assert_called_once()


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.create.configure_repo_url_secret")
@patch("automl.cli.create.GitURL")
@patch("automl.cli.create.set_k8s_auth")
@patch("automl.cli.create.create_cronworkflow_runner")
def test_create_cronworkflow(
    mock_create_cronorkflow,
    mock_set_k8s,
    mock_git,
    mock_configure_secret,
    mock_load_k8s,
):
    mock_load_k8s.side_effect = None
    _ = CliRunner().invoke(
        create_cli,
        [
            "cronworkflow", "name", "url-repo",
            "--schedule", "* * * * *",
            "--token", "token",
            "--branch", "master",
            "--namespace", "namespace",
            "--file", "config.yaml"
        ]
    )
    mock_set_k8s.assert_called_once()
    mock_git.assert_called_once()
    mock_configure_secret.assert_called_once()
    mock_create_cronorkflow.assert_called_once()


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.update.update_workflow_secret")
def test_update_secret(
    mock_update_secret,
    mock_load_k8s,
):
    mock_load_k8s.side_effect = None
    _ = CliRunner().invoke(
        update_cli,
        [
            "secret", "foo", "FOO=bar,BOO=baz",
            "--namespace", "namespace",
        ]
    )
    mock_update_secret.assert_called_once()


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.update.configure_repo_url_secret")
@patch("automl.cli.update.GitURL")
@patch("automl.cli.update.set_k8s_auth")
@patch("automl.cli.update.update_cronworkflow_runner")
def test_update_cronworkflow(
    mock_update_cronorkflow,
    mock_set_k8s,
    mock_git,
    mock_configure_secret,
    mock_load_k8s,
):
    mock_load_k8s.side_effect = None

    _ = CliRunner().invoke(
        update_cli,
        [
            "cronworkflow", "workflow-name", "url-repo",
            "--namespace", "namespace",
        ]
    )
    mock_set_k8s.assert_called_once()
    mock_git.assert_called_once()
    mock_configure_secret.assert_called_once()
    mock_update_cronorkflow.assert_called_once()


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.delete.delete_workflow_secret")
def test_delete_secret(
    mock_delete,
    mock_load_k8s
):
    mock_load_k8s.side_effect = None
    _ = CliRunner().invoke(
        delete_cli,
        ["secret", "foo", "--namespace", "namespace"]
    )
    mock_delete.assert_called_once()


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.delete.delete_resources")
def test_delete_workflow(
    mock_delete,
    mock_load_k8s
):
    mock_load_k8s.side_effect = None
    _ = CliRunner().invoke(
        delete_cli,
        ["workflow", "workflow-name", "--namespace", "namespace"]
    )
    mock_delete.assert_called_once()


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.get.get_runner_logs")
@patch("automl.cli.get.runner_exists")
@patch("automl.cli.get.tabulate_data")
def test_get_workflow(
    mock_tabulate_data,
    mock_runner_exists,
    mock_get_runner_logs,
    mock_load_k8s
):
    runner = CliRunner()
    mock_load_k8s.side_effect = None
    mock_runner_exists.return_value = True

    _ = runner.invoke(
        get_cli,
        [
            "workflow", "workflow-name",
            "--namespace", "namespace",
        ]
    )
    mock_tabulate_data.assert_called()

    _ = runner.invoke(
        get_cli,
        [
            "workflow", "workflow-name",
            "--namespace", "namespace",
            "--logs"
        ]
    )

    mock_get_runner_logs.assert_called_once_with(
        "workflow-name", "namespace"
    )


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.get.tabulate_secrets")
def test_get_secrets(mock_tabulate_secrets, mock_load_k8s):
    mock_load_k8s.side_effect = None

    _ = CliRunner().invoke(
        get_cli,
        ["secrets", "--namespace", "namespace"]
    )
    mock_tabulate_secrets.assert_called()


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.get.get_runner_logs")
@patch("automl.cli.get.cron_runner_exists")
@patch("automl.cli.get.tabulate_data")
def test_get_cronworkflow(
    mock_tabulate_data,
    mock_cron_runner_exists,
    mock_get_runner_logs,
    mock_load_k8s
):
    runner = CliRunner()
    mock_load_k8s.side_effect = None
    mock_cron_runner_exists.return_value = True

    _ = runner.invoke(
        get_cli,
        [
            "cronworkflow", "cronworkflow-name",
            "--namespace", "namespace",
        ]
    )
    mock_tabulate_data.assert_called()

    _ = runner.invoke(
        get_cli,
        [
            "cronworkflow", "cronworkflow-name",
            "--namespace", "namespace",
            "--logs"
        ]
    )

    mock_get_runner_logs.assert_called_once_with(
        "cronworkflow-name", "namespace", type_of_job="cronjob"
    )


@patch("kubernetes.config.load_kube_config")
@patch("automl.cli.run.run")
@patch("automl.cli.run.download_config")
@patch("automl.cli.run.create_and_validate_config")
def test_run_workflow(
    mock_create_config,
    mock_download_config,
    mock_run,
    mock_load_k8s
):
    mock_load_k8s.side_effect = None
    _ = CliRunner().invoke(
        run_cli,
        [
            "--workflow", "workflow",
            "--project-dir", "dir",
            "--branch", "master",
            "--namespace", "namespace",
        ]
    )
    mock_download_config.assert_called_once()
    mock_create_config.assert_called_once()
    mock_run.assert_called_once()
