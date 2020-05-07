from kubernetes import client

from .utils import get_deployment_name


def create_ingress_object(
    workflow_name: str,
    namespace: str,
    stage_name: str,
    step_name: str,
    port: int = 8080,
    **kwargs
) -> client.V1Ingress:
    """Create an ingress object.

    :param workflow_name: The name of the current workflow.
    :param namespace: The name of the Kubernetes namespace.
    :param stage_name: The name of the current stage.
    :param step_name: The name of the current step.
    :param port: The number of the port the service becomes visible on.

    :return: Kubernetes V1Ingress object.
    """
    service_name = get_deployment_name(workflow_name, stage_name, step_name)
    path = "/{0}/{1}-{2}-{3}".format(
        namespace, workflow_name, stage_name, step_name
    )

    metadata = client.V1ObjectMeta(
        namespace=namespace,
        name=get_deployment_name(workflow_name, stage_name, step_name),
        annotations={
            "kubernetes.io/ingress.class": "nginx",
            "nginx.ingress.kubernetes.io/rewrite-target": "/$1",
        },
        labels={
            "app": "automl",
            "workflow": workflow_name,
            "stage": stage_name,
            "step": step_name
        }
    )

    spec = client.V1IngressSpec(
        rules=[client.V1IngressRule(
            http=client.V1HTTPIngressRuleValue(
                paths=[client.V1HTTPIngressPath(
                    path=path,
                    path_type="Exact",
                    backend=client.V1IngressBackend(
                        service=client.V1IngressServiceBackend(
                            name=service_name,
                            port=client.V1ServiceBackendPort(
                                number=port
                            ),
                        )
                    ),
                )]
            )
        )]
    )

    ingress = client.V1Ingress(
        # Works for Kubernetes cluster versions >= 1.19
        api_version="networking.k8s.io/v1",
        kind="Ingress",
        metadata=metadata,
        spec=spec
    )
    return ingress


def create_ingress(ingress: client.V1Ingress) -> None:
    """Create the specified ingress in the k8s namespace.

    :param ingress: A configured ingress object.
    """
    client.NetworkingV1Api().create_namespaced_ingress(
        namespace=ingress.metadata.namespace,
        body=ingress
    )


def delete_ingresses(namespace: str, workflow_name: str = None) -> None:
    """Delete an ingress to a service backed by a deployment.

    :param namespace: Namespace in which exists the ingress to delete.
    :param workflow_name: The name of the workflow.
    """
    ingess_objects = client.NetworkingV1Api().list_namespaced_ingress(
        label_selector=(
            f"app=automl,workflow={workflow_name}"
            if workflow_name else "app=automl"
        ),
        namespace=namespace
    ).items

    for ingress_object in ingess_objects:
        client.NetworkingV1Api().delete_namespaced_ingress(
            name=ingress_object.metadata.name,
            namespace=namespace,
            propagation_policy="Background"
        )


def ingress_exists(ingress_name: str, namespace: str) -> bool:
    """Check if the specified ingress exists in the k8s namespace.

    :param ingress_name: The name of the ingress to check.
    :param namespace: The name of the kubernetes namespace.

    :return: True if the ingress was found, otherwise False.
    """
    ingress_objects = client.NetworkingV1Api().list_namespaced_ingress(
        namespace=namespace
    ).items

    ingress_names = [
        ingress_object.metadata.name for ingress_object in ingress_objects
    ]

    return True if ingress_name in ingress_names else False
