import typing as t
from kubernetes import client

from automl.exceptions import StopWorkflowExecution


def create_secret_object(
    name: str,
    data: t.Dict[str, str],
    namespace: str,
    workflow_name: str = None,
    type: str = None
) -> client.V1Secret:
    """Create a secret object.

    :param name: The name of the secret.
    :param data: Dictionary of the parsed key-value pairs.
    :param namespace: The name of the Kubernetes namesapce.
    :param workflow_name: The name of the current workflow.
    :param type: Type of the secret.
                 See https://kubernetes.io/docs/concepts/configuration/secret/#secret-types

    :return: Kubernetes V1Secret object.
    """
    secret_object = client.V1Secret(
        metadata=client.V1ObjectMeta(
            namespace=namespace,
            name=name,
            labels={
                "app": "automl",
                "workflow": workflow_name
            },
        ),
        string_data=data,
        type=type
    )

    return secret_object


def create_secret(
    name: str,
    data: t.Dict[str, str],
    namespace: str,
    workflow_name: str = None,
    type: str = None
) -> None:
    """Create a secret in the k8s namespace.

    :param name: The name of the secret.
    :param data: Dictionary of the parsed key-value pairs.
    :param namespace: The name of the Kubernetes namesapce.
    :param workflow_name: The name of the current workflow.
    :param type: Type of the secret.
                See https://kubernetes.io/docs/concepts/configuration/secret/#secret-types
    """
    secret_object = create_secret_object(
        name, data, namespace,
        workflow_name=workflow_name, type=type
    )

    client.CoreV1Api().create_namespaced_secret(
        body=secret_object,
        namespace=namespace
    )


def update_secret(
    name: str,
    data: t.Dict[str, str],
    namespace: str,
) -> None:
    """Update the secret in the k8s namespace.

    :param name: The name of the secret.
    :param data: Dictionary of the parsed key-value pairs.
    :param namespace: The name of the Kubernetes namesapce.
    """
    stale_secret_object = client.CoreV1Api().read_namespaced_secret(
        name=name, namespace=namespace
    )

    updated_data = (
        {**stale_secret_object.data, **data}
        if stale_secret_object.data
        else data
    )

    secret_object = create_secret_object(
        name,
        updated_data,
        namespace,
        workflow_name=stale_secret_object.metadata.labels["workflow"],

    )

    client.CoreV1Api().patch_namespaced_secret(
        name=name,
        namespace=namespace,
        body=secret_object
    )


def delete_secrets(
    namespace: str,
    workflow_name: str = None,
    name: str = None
) -> None:
    """Delete secrets in the k8s namespace.

    :param namespace: The name of the Kubernetes namesapce.
    :param workflow_name: The name of the current workflow.
    :param name: The name of the secret.
    """
    if name:
        client.CoreV1Api().delete_namespaced_secret(
            name=name,
            namespace=namespace
        )
    if workflow_name:
        secret_objects = client.CoreV1Api().list_namespaced_secret(
            namespace=namespace,
            label_selector=(
                f"app=automl,workflow={workflow_name}"
            )
        ).items

        for secret in secret_objects:
            client.CoreV1Api().delete_namespaced_secret(
                name=secret.metadata.name,
                namespace=namespace
            )


def secret_exists(name: str, namespace: str) -> bool:
    """Check if the specified secret exists in the k8s namespace.

    :param name: The name of the secret to check.
    :param namespace: The name of the kubernetes namespace.

    :return: True if the secret was found, otherwise False.
    """
    secret_objects = client.CoreV1Api().list_namespaced_secret(
        namespace=namespace
    ).items

    secret_names = [
        secret_object.metadata.name
        for secret_object in secret_objects
    ]
    return True if name in secret_names else False


def list_secrets(namespace: str = None) -> t.List[t.Dict[str, str]]:
    """List of the secret info dictionaries within the specified workflow.

    :param namespace: The name of the Kubernetes namespace.
    """
    secret_objects = client.CoreV1Api().list_namespaced_secret(
        namespace=namespace,
        label_selector="app=automl"
    ).items

    list_of_secrets = []
    for secret_object in secret_objects:
        info = {}
        info["name"] = secret_object.metadata.name
        info["namespace"] = secret_object.metadata.namespace
        info["workflow"] = secret_object.metadata.labels["workflow"]
        info["keys"] = (
            [key for key in secret_object.data.keys()]
            if secret_object.data else []
        )
        list_of_secrets.append(info)

    return list_of_secrets


def create_envs_from_secrets(
    secret_names: t.List[str],
    namespace: str
) -> t.List[client.V1EnvVar]:
    """Create env variables from the secrtes to put in the pods.

    :param secret_name: The name of the secrets to put in the pods.
    :param namespace: The name of the Kubernetes namespace.

    :return: List of the V1Client objects.
    """
    secret_objects = client.CoreV1Api().list_namespaced_secret(
        namespace=namespace,
        label_selector="app=automl"
    ).items

    all_secret_names = [
        secret_object.metadata.name
        for secret_object in secret_objects
    ]

    secrets_not_found = [
        secret_name
        for secret_name in secret_names
        if secret_name not in all_secret_names
    ]

    if len(secrets_not_found) > 0:
        msg = (
            ", ".join(secrets_not_found)
            + f" secret(-s) was/were not found in {namespace} namespace"
        )
        raise StopWorkflowExecution(msg)

    envs = [
        client.V1EnvFromSource(
            secret_ref=client.V1SecretEnvSource(
                name=name
            )
        ) for name in secret_names
    ]

    return envs


def get_docker_secret_name(namespace: str) -> client.V1LocalObjectReference:
    """Get the name of the dockerconfigjson type.

    In case there are several docker secrets,
    the last created secret will be used.

    :param namespace: The name of the Kubernetes namespace.

    :return: Kubernetes V1LocalObjectReference object.
    """
    secret_objects = sorted(
        client.CoreV1Api().list_namespaced_secret(
            namespace=namespace,
            label_selector="app=automl",
            field_selector="type=kubernetes.io/dockerconfigjson"
        ).items,
        key=lambda x: x.metadata.creation_timestamp,  # type: ignore
        reverse=True
    )

    secret_names = [
        secret_object.metadata.name
        for secret_object in secret_objects
    ]

    k8s_reference = (
        client.V1LocalObjectReference(name=secret_names[0])
        if secret_names
        else None
    )
    return k8s_reference


def get_repo_url_secret_name(workflow_name: str) -> str:
    return f"repo-{workflow_name}"
