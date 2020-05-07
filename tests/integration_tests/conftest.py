import os
import re

from pytest import fixture
from kubernetes import client, config
from automl.defaults import (
    CLIENT_DOCKER_IMAGE_REPO,
    DOCKER_IMAGE_REPO,
    AUTOML_NAMESPACE,
    AUTOML_CLUSTER_ROLE,
    AUTOML_CLUSTER_ROLE_BINDING,
    NGINX_CONTROLLER_NAMESPACE,
    NGINX_CONTROLLER_NAME
)
from automl.version import VERSION
from automl.processing.config import StepConfig
from automl.k8s.namespace import create_namespace, delete_namespace
from automl.k8s.authorization import set_k8s_auth

RE_IP = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')


@fixture(scope="session", autouse=True)
def check_basic_docker_images():
    tag = os.getenv("DOCKER_TEST_TAG", VERSION)
    docker_image = f"{DOCKER_IMAGE_REPO}:{tag}"
    client_docker_image = f"{CLIENT_DOCKER_IMAGE_REPO}:{tag}"
    StepConfig.check_image(docker_image)
    StepConfig.check_image(client_docker_image)
    yield


@fixture(scope="session", autouse=True)
def configure_cluster():
    config.load_kube_config()
    create_namespace(AUTOML_NAMESPACE)
    set_k8s_auth(AUTOML_NAMESPACE)

    yield

    delete_namespace(AUTOML_NAMESPACE)
    client.RbacAuthorizationV1Api().delete_cluster_role(
        AUTOML_CLUSTER_ROLE
    )
    client.RbacAuthorizationV1Api().delete_cluster_role_binding(
        AUTOML_CLUSTER_ROLE_BINDING
    )


@fixture(scope="function")
def load_balancer_ip_or_hostname():
    config.load_kube_config()
    _, active_context = config.list_kube_config_contexts()
    if active_context["name"] == "minikube":
        address = RE_IP.findall(
            client.Configuration.get_default_copy().host
        )[0]
    else:
        try:
            service_objects = client.CoreV1Api().list_namespaced_service(
                namespace=NGINX_CONTROLLER_NAMESPACE
            )
            service = [
                service
                for service in service_objects.items
                if service.metadata.name == NGINX_CONTROLLER_NAME
            ][0]
            address = service.status.load_balancer.ingress[0].hostname
        except IndexError as e:
            raise RuntimeError(
                f"Cannot find ingress controller in "
                f"{NGINX_CONTROLLER_NAMESPACE} namespace."
            ) from e
        except AttributeError as e:
            raise RuntimeError(
                f"No load balancer to expose the NGINX Ingress controller "
                f"was found in {NGINX_CONTROLLER_NAMESPACE} namespace "
            ) from e
    yield address
