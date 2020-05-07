

def get_deployment_name(
    workflow_name: str,
    stage_name: str,
    step_name: str
) -> str:
    return f"{workflow_name}-{stage_name}-{step_name}"
