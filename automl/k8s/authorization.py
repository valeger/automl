import os
import logging

from kubernetes import client, config

from automl.defaults import (
    AUTOML_SERVICE_ACCOUNT,
    AUTOML_CLUSTER_ROLE,
    AUTOML_CLUSTER_ROLE_BINDING
)

from .namespace import create_namespace, namespace_exists

logger = logging.getLogger("automl")


def load_kube_config() -> None:
    """Load k8s configuration file.

    if running whithin a cluster, cluster initialization can be
    preformed via in-cluster config. Otherwise initialization will
    be preformed via ~/.kube/config file.
    """
    if os.getenv("KUBERNETES_SERVICE_HOST"):
        logger.info("Loading in-cluster config (from a runner).")
        config.load_incluster_config()
    else:
        config.load_kube_config()


def set_k8s_auth(
    namespace: str,
    service_account_name: str = AUTOML_SERVICE_ACCOUNT,
    controller_name: str = AUTOML_CLUSTER_ROLE,
    grantor_name: str = AUTOML_CLUSTER_ROLE_BINDING
) -> None:
    """Setup k8s cluster with required roles and service accounts.

    When running automl runner, initially the pod is not authorized.
    For eventual usage some policies must be granted to the pod via
    ServiceAccount and ClusterRole.

    :param namespace: The name of the kubernetes namespace.
    :param service_account_name: The name of the ServiceAccount
    :param controller_name: The name of the ClusterRole.
    :param grantor_name: The name of the ClusterRoleBinding.
    """
    if not namespace_exists(namespace):
        logger.info(f"Creating namespace {namespace}")
        create_namespace(
            namespace=namespace
        )

    if not service_account_exists(service_account_name, namespace):
        logger.info(
            "Creating service account={0} within namespace {1}".format(
                service_account_name, namespace
            )
        )
        create_service_account(
            service_account_name=service_account_name,
            namespace=namespace
        )

    if not cluster_role_exists(controller_name):
        logger.info(
            "Creating cluster role {0}".format(controller_name)
        )
        create_cluster_role(controller_name, namespace)

    if not cluster_role_binding_exists(grantor_name):
        logger.info(
            "Creating cluster role binding={0} to bind {1} cluster role "
            "with service account {2} within {3} namespace.".format(
                grantor_name, controller_name, service_account_name, namespace
            )
        )
        create_cluster_role_binding(
            service_account_name=service_account_name,
            grantor_name=grantor_name,
            controller_name=controller_name,
            namespace=namespace
        )


def create_service_account(
    service_account_name: str,
    namespace: str,
) -> None:
    """Create a service-account with required roles

    When running automl runner, initially the pod is not authorized.
    For eventual usage some policies must be granted to the pod via
    ServiceAccount and ClusterRole.

    :param service_account_name: The name of the ServiceAccount
    :param namespace: Namespace in which the ServiceAccount will be placed.
    """
    service_account_object = client.V1ServiceAccount(
        metadata=client.V1ObjectMeta(
            namespace=namespace, name=service_account_name
        )
    )
    client.CoreV1Api().create_namespaced_service_account(
        namespace=namespace, body=service_account_object
    )


def service_account_exists(service_account_name: str, namespace: str) -> bool:
    """Check if the ServiceAccount exists within the namespace.

    :param service_account_name: The name of the ServiceAccount to check.
    :param namespace: The name of the kubernetes namespace.
    :return: True if the ServiceAccount was found, otherwise False.
    """
    service_account_objects = (
        client.CoreV1Api().list_namespaced_service_account(namespace=namespace)
    ).items

    service_account_names = [
        service_account_object.metadata.name
        for service_account_object in service_account_objects
    ]
    return True if service_account_name in service_account_names else False


def create_cluster_role(controller_name: str, namespace: str) -> None:
    """Create a ClusterRole with the specified policies.

    :param controller_name: The name of the ClusterRole to create.
    :param namespace: The name of the kubernetes namespace.
    """
    cluster_role_object = client.V1ClusterRole(
        metadata=client.V1ObjectMeta(
            name=controller_name,
            namespace=namespace
        ),
        rules=[
            client.V1PolicyRule(
                api_groups=[""],
                resources=["namespaces", "services"],
                verbs=["get", "list", "create", "delete"],
            ),
            client.V1PolicyRule(
                api_groups=[""],
                resources=["serviceaccounts"],
                verbs=["list", "create"],
            ),
            client.V1PolicyRule(
                api_groups=[""],
                resources=["pods", "pods/log"],
                verbs=["get", "list"]
            ),
            client.V1PolicyRule(
                api_groups=[""],
                resources=["configmaps"],
                verbs=["get", "list"],
            ),
            client.V1PolicyRule(
                api_groups=[""],
                resources=["secrets"],
                verbs=["get", "list", "create", "update", "patch"],
            ),
            client.V1PolicyRule(
                api_groups=["rbac.authorization.k8s.io"],
                resources=["roles", "rolebindings"],
                verbs=["create"],
            ),
            client.V1PolicyRule(
                api_groups=["rbac.authorization.k8s.io"],
                resources=["clusterrolebindings"],
                verbs=["get", "list", "create"],
            ),
            client.V1PolicyRule(
                api_groups=["apps", "batch", "core"],
                resources=["*"],
                verbs=["*"]
            ),
            client.V1PolicyRule(
                api_groups=["networking.k8s.io", "extensions"],
                resources=["ingresses"],
                verbs=["*"],
            ),
        ],
    )
    client.RbacAuthorizationV1Api().create_cluster_role(body=cluster_role_object)


def cluster_role_exists(controller_name: str) -> bool:
    """Check if the ClusterRole exists.

    :param controller_name: The name of the ClusterRole to check.
    :return: True if the ClusterRole was found, otherwise False.
    """
    cluster_role_objects = (
        client.RbacAuthorizationV1Api().list_cluster_role()
    ).items

    cluster_role_names = [
        cluster_role_object.metadata.name
        for cluster_role_object in cluster_role_objects
    ]
    return True if controller_name in cluster_role_names else False


def create_cluster_role_binding(
    service_account_name: str,
    grantor_name: str,
    controller_name: str,
    namespace: str,
) -> None:
    """Create a ClusterRoleBinding.

    :param service_account_name: The name of the ServiceAccount to grant ClusterRole.
    :param grantor_name: The name of the ClusterRoleBinding to create.
    :param controller_name: The name of the ClusterRole to bind.
    :param namespace: The name of the kubernetes namespace.
    """
    cluster_role_binding_object = client.V1ClusterRoleBinding(
        metadata=client.V1ObjectMeta(
            name=grantor_name,
            namespace=namespace
        ),
        role_ref=client.V1RoleRef(
            kind="ClusterRole",
            name=controller_name,
            api_group="rbac.authorization.k8s.io",
        ),
        subjects=[
            client.V1Subject(
                kind="ServiceAccount",
                name=service_account_name,
                namespace=namespace,
            )
        ],
    )
    client.RbacAuthorizationV1Api().create_cluster_role_binding(
        body=cluster_role_binding_object
    )


def cluster_role_binding_exists(grantor_name: str) -> bool:
    """Check if the ClusterRoleBinding exists.

    :param grantor_name: The name of the ClusterRoleBinding to check.
    :return: True if the ClusterRoleBinding was found, otherwise False.
    """
    cluster_role_binding_objects = (
        client.RbacAuthorizationV1Api().list_cluster_role_binding()
    ).items

    cluster_role_binding_names = [
        cluster_role_binding_object.metadata.name
        for cluster_role_binding_object in cluster_role_binding_objects
    ]
    return True if grantor_name in cluster_role_binding_names else False
