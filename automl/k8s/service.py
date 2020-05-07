import typing as t
from kubernetes import client
from .utils import get_deployment_name


def create_service_object(
    workflow_name: str,
    namespace: str,
    stage_name: str,
    step_name: str,
    port: int = None,
    **kwargs: t.Any
) -> client.V1Service:
    """Create a service object.

    :param workflow_name: The name of the current workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param stage_name: The name of the current stage.
    :param step_name: The name of the current step.
    :param port: The port on the pod that the request gets sent to
                 (== targetPort of the kubernetes service).
    """
    spec = client.V1ServiceSpec(
        type="NodePort",
        selector={
            "app": "automl",
            "workflow": workflow_name,
            "stage": stage_name,
            "step": step_name
        },
        ports=[client.V1ServicePort(port=port, target_port=port)],
    )

    metadata = client.V1ObjectMeta(
        namespace=namespace,
        name=get_deployment_name(workflow_name, stage_name, step_name),
        labels={
            "app": "automl",
            "workflow": workflow_name,
            "stage": stage_name,
            "step": step_name
        }
    )

    service = client.V1Service(
        api_version="v1",
        kind="Service",
        metadata=metadata,
        spec=spec
    )
    return service


def create_service(service: client.V1Service) -> None:
    """Create the specified service in the k8s namespace.

    :param service: A configured service object.
    """
    client.CoreV1Api().create_namespaced_service(
        namespace=service.metadata.namespace,
        body=service
    )


def service_exists(service_name: str, namespace: str) -> bool:
    """Check if the specified service exists in the k8s namespace.

    :param service_name: The name of the service to check.
    :param namespace: The name of the kubernetes namespace.

    :return: True if the service was found, otherwise False
    """
    service_objects = client.CoreV1Api().list_namespaced_service(
        namespace=namespace
    ).items

    service_names = [
        service_object.metadata.name for service_object in service_objects
    ]

    return True if service_name in service_names else False


def delete_services(namespace: str, workflow_name: str = None) -> None:
    """Delete a service backed by a deployment.

    :param namespace: Namespace in which exists the service to delete.
    :param workflow_name: The name of the workflow.
    """
    service_objects = client.CoreV1Api().list_namespaced_service(
        label_selector=(
            f"app=automl,workflow={workflow_name}"
            if workflow_name else "app=automl"
        ),
        namespace=namespace
    ).items

    for service_object in service_objects:
        client.CoreV1Api().delete_namespaced_service(
            name=service_object.metadata.name,
            namespace=namespace,
            propagation_policy="Background"
        )
