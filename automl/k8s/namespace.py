from kubernetes import client


def namespace_exists(namespace: str) -> bool:
    """Check if the namespace exists on the Kubernetes cluster.

    :param namespace: The name of the Kubernetes namespace to check.
    :return: True if the namespace was found, otherwise False.
    """
    namespace_objects = (
        client.CoreV1Api().list_namespace()
    ).items

    namespace_names = (
        namespace_object.metadata.name
        for namespace_object in namespace_objects
    )

    return True if namespace in namespace_names else False


def create_namespace(namespace: str) -> None:
    """Create the new namespace.

    :param namespace: The nmae of the Kubernetes namespace to create.
    """
    client.CoreV1Api().create_namespace(
        body=client.V1Namespace(
            api_version="v1",
            kind="Namespace",
            metadata=client.V1ObjectMeta(name=namespace)
        )
    )


def delete_namespace(namespace: str) -> None:
    """Delete the specified namespace.

    :param namespace: The name of the Kubernetes namespace to delete.
    """
    client.CoreV1Api().delete_namespace(
        name=namespace,
        propagation_policy="Background"
    )
