import os
from pathlib import Path
from automl.version import VERSION

ROOT_PACKAGE = Path(__file__).parent.resolve()

AUTOML_NAMESPACE: str = "automl"
AUTOML_SERVICE_ACCOUNT: str = f"{AUTOML_NAMESPACE}-service-account"
AUTOML_CLUSTER_ROLE: str = f"{AUTOML_NAMESPACE}-controller"
AUTOML_CLUSTER_ROLE_BINDING: str = f"{AUTOML_NAMESPACE}-granter"

CONTAINER_NAME: str = "automl"

DOCKER_IMAGE_REPO: str = "valeger/automl"
DOCKER_IMAGE_TAG = CLIENT_IMAGE_TAG = os.getenv("DOCKER_TEST_TAG", VERSION)
DOCKER_IMAGE: str = f"{DOCKER_IMAGE_REPO}:{DOCKER_IMAGE_TAG}"
CLIENT_DOCKER_IMAGE_REPO: str = "valeger/automl-client"
CLIENT_DOCKER_IMAGE: str = f"{CLIENT_DOCKER_IMAGE_REPO}:{CLIENT_IMAGE_TAG}"

DOCKER_API_URL: str = "https://hub.docker.com/v2/repositories/{username}{repo}/tags/{tag}"

NGINX_CONTROLLER_NAMESPACE: str = "ingress-nginx"
NGINX_CONTROLLER_NAME: str = "ingress-nginx-controller"

RUNNER_TTL_AFTER_FINISHED: int = 604800
RUNNER_SUCCESS_JOBS_LIMIT: int = 2
RUNNER_FAILED_JOBS_LIMIT: int = 2
RUNNER_BACKOFF_LIMIT: int = 2
