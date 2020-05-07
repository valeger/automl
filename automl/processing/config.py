"""Validation module for configuration file (yaml)"""
from __future__ import annotations
from typing import Dict, Optional, List
import re
from yaml import safe_load
import requests

from pydantic import (
    BaseModel,
    validator,
    conint,
    confloat,
)

from .utils import validate_schedule, fix_k8s_name
from automl.exceptions import AutomlOSError
from automl.defaults import DOCKER_API_URL, CLIENT_DOCKER_IMAGE
from automl.version import VERSION


RE_MODULE_PATH = re.compile(r"^.+\.(py|ipynb)$")
RE_DEPENDENCY_PATH = re.compile(r".+\.txt$")
RE_DOCKER_IMAGE = re.compile(r"([\w._-]+/)?([\w._-]+):?([\w._-]+)?$")


class Service(BaseModel):
    """Service Config"""
    port: int = 5000
    ingress: bool = False


class StepConfig(BaseModel):
    """Step Config"""
    step_name: str
    path_to_executable: str
    dependency_path: str
    image: str = CLIENT_DOCKER_IMAGE
    command: Optional[List[str]]
    envs: Optional[Dict[str, str]]
    secrets: List[str] = []
    cpu_request: confloat(gt=0) = 0.5         # type: ignore
    memory_request: conint(gt=0) = 500        # type: ignore
    replicas: conint(gt=0) = 2                # type: ignore
    backoff_limit: conint(ge=0) = 0           # type: ignore
    revision_history_limit: conint(ge=0) = 2  # type: ignore
    timeout: conint(gt=0) = 30                # type: ignore
    polling_time: conint(gt=0) = 1            # type: ignore
    wait_before_start_time: conint(gt=0) = 5  # type: ignore
    min_ready_seconds: conint(gt=0) = 5       # type: ignore
    service: Optional[Service]

    @validator("step_name")
    def fix_step_name(cls, step_name):
        return fix_k8s_name(step_name)

    @validator("path_to_executable")
    def check_module_path(cls, path):
        if RE_MODULE_PATH.match(path):
            return path
        raise AutomlOSError(
            f"Incorrect path in configuration file: {path}. "
            "Files must have py or ipynb extension"
        )

    @validator("dependency_path")
    def check_dependency_path(cls, path):
        if RE_DEPENDENCY_PATH.match(path):
            return path
        raise AutomlOSError(
            f"Incorrect path in configuration file: {path}. "
            "Only txt extension is supported."
        )

    @validator("image")
    def check_image(cls, image):
        try:
            username, repo, tag = RE_DOCKER_IMAGE.findall(image)[0]
            username = username if username else "library/"
            tag = tag if tag else "latest"
            url = DOCKER_API_URL.format(
                username=username, repo=repo, tag=tag
            )
            response = requests.head(url, allow_redirects=True)
            response.raise_for_status()
        except requests.HTTPError as e:
            msg = (
                f"Cannot connect to docker repository: {url} "
                f"(code {response.status_code})"
            )
            raise requests.HTTPError(msg) from e
        return f"{username}{repo}:{tag}"

    @validator("secrets")
    def check_secrets(cls, secrets):
        return [fix_k8s_name(secret) for secret in secrets]


class Config(BaseModel):
    """Base config"""
    version: str = VERSION
    name: Optional[str]
    schedule: Optional[str]
    stages: Dict[str, List[StepConfig]]

    @validator("name")
    def fix_name(cls, name):
        return fix_k8s_name(name)

    @validator("schedule")
    def check_schedule(cls, schedule):
        validate_schedule(schedule)

    @validator("stages")
    def fix_stage_name(cls, stages: dict):
        return dict(
            [(fix_k8s_name(key), value) for key, value in stages.items()]
        )


def create_and_validate_config(unparsed_config: bytes) -> Config:
    """Validate configuration."""
    parsed_config = safe_load(unparsed_config) or {}
    _config = Config(**parsed_config)

    return _config
