import pytest
import requests
from pathlib import Path

import pydantic

from automl.processing.config import StepConfig, create_and_validate_config
from automl.processing.utils import fix_k8s_name, validate_schedule
from automl.exceptions.automl_exceptions import AutomlValueError, AutomlOSError

PATH_CONFIG = Path(__file__).parent.parent.joinpath("data", "configs").resolve()


@pytest.mark.parametrize(
    "image,checked_image",
    [
        ("ubuntu:14.04", "library/ubuntu:14.04"),
        ("logstash:8.1.0", "library/logstash:8.1.0"),
        ("valeger/dagster-delta:load-and-train", "valeger/dagster-delta:load-and-train"),
        ("docker.io/library/ubuntu:20.04", "library/ubuntu:20.04"),
        ("elasticsearch:8.1.0", "library/elasticsearch:8.1.0"),
        ("fluent/fluent-bit", "fluent/fluent-bit:latest")
    ]
)
def test_check_image(image, checked_image):
    assert StepConfig.check_image(image) == checked_image


@pytest.mark.parametrize(
    "image",
    [
        "docker.elastic.co/elasticsearch/elasticsearch",
        "docker.elastic.co/kibana/kibana",
        "elasticsearch",
        "logstash",
        "gcr.io/k8s-minikube/kicbase",
    ]
)
def test_check_image_with_error(image):
    with pytest.raises(requests.exceptions.HTTPError):
        StepConfig.check_image(image)


@pytest.mark.parametrize(
    "name,fixed_name",
    [
        ("ml_train_k8s", "ml-train-k8s"),
        ("name/space", "name-space"),
        ("myapp$$$///1234", "myapp-1234"),
        ("foo/boo", "foo-boo"),
        ("f#oo", "f-oo"),
        ("foo.bar-cdb8b9694-rtfbx", "foo.bar-cdb8b9694-rtfbx"),
        ("backend", "backend"),
        ("kubernetes**name///space", "kubernetes-name-space"),
        ("==prod_namespace==", "prod-namespace"),
    ]
)
def test_fix_k8s_name(name, fixed_name):
    assert fix_k8s_name(name) == fixed_name


@pytest.mark.parametrize(
    "schedule,valid_schedule",
    [
        ("* * * * *", "* * * * *"),
        ("0 * * * *", "0 * * * *"),
        ("*/8 * * * *", "*/8 * * * *"),
        ("0,15,30 * * * *", "0,15,30 * * * *"),
        ("15-45 * * * *", "15-45 * * * *"),
        ("15-45/5 * * * *", "15-45/5 * * * *"),
        ("* 0 * * *", "* 0 * * *"),
        ("* */5 * * *", "* */5 * * *"),
        ("* 0,6,12 * * *", "* 0,6,12 * * *"),
        ("* 6-18 * * *", "* 6-18 * * *"),
        ("* 6-18/5 * * *", "* 6-18/5 * * *"),
        ("* * 0 * *", "* * 0 * *"),
        ("* * */8 * *", "* * */8 * *"),
        ("* * 0,10,20 * *", "* * 0,10,20 * *"),
        ("* * 15-30 * *", "* * 15-30 * *"),
        ("* * 15-30/5 * *", "* * 15-30/5 * *"),
        ("* * * 0 *", "* * * 0 *"),
        ("* * * */8 *", "* * * */8 *"),
        ("* * * 0,5,10 *", "* * * 0,5,10 *"),
        ("* * * 6-12 *", "* * * 6-12 *"),
        ("* * * 6-12/2 *", "* * * 6-12/2 *"),
        ("* * * * 1", "* * * * 1"),
        ("* * * * */2", "* * * * */2"),
        ("* * * * 0-4", "* * * * 0-4"),
        ("* * * * 0-6/2", "* * * * 0-6/2"),
    ]
)
def test_validate_schedule(schedule, valid_schedule):
    assert validate_schedule(schedule) == valid_schedule


@pytest.mark.parametrize(
    "schedule",
    [
        "* * * *", "b * * * *", "* b * * *",
        "* * b * *", "* * * b *", "* * * * b",
        "65 * * * *", "8/8 * * * *", "* * * * 7",
        "0,15,30/5 * * * *", "15-30-45 * * * *",
        "* 28 * * *", "* 24 * * *", "* 0-6-12 * * *",
        "* * * 13 *", "* * * 0,6-12 *", "* * * 0-6-12 *",
        "* * * * 7", "* * * * 0,6/3", "* * * * 0-3-6"
    ]
)
def test_validate_schedule_with_error(schedule):
    with pytest.raises(AutomlValueError):
        validate_schedule(schedule)


def test_create_and_validate_config():
    with open(PATH_CONFIG / "config_without_errors.yaml", 'rb') as file:
        unparsed_config = file.read()
    config = create_and_validate_config(unparsed_config)
    assert config.stages


@pytest.mark.parametrize(
    "path",
    ["train.py", "train.ipynb"]
)
def test_check_module_path(path):
    assert StepConfig.check_module_path(path)


@pytest.mark.parametrize(
    "path",
    ["train.h", "train.sc", "train.yaml"]
)
def test_check_module_path_with_error(path):
    with pytest.raises(AutomlOSError):
        StepConfig.check_module_path(path)


@pytest.mark.parametrize(
    "path",
    ["config.yaml", "conda.json"]
)
def test_check_dependency_path_with_error(path):
    with pytest.raises(AutomlOSError):
        StepConfig.check_module_path(path)


def test_create_and_validate_config_with_error():
    with open(PATH_CONFIG / "config_with_errors.yaml", 'rb') as file:
        unparsed_config = file.read()

    with pytest.raises((AutomlValueError, requests.exceptions.HTTPError)):
        create_and_validate_config(unparsed_config)

    with open(PATH_CONFIG / "config_empty.yaml", 'rb') as file:
        unparsed_config = file.read()

    with pytest.raises(pydantic.ValidationError):
        create_and_validate_config(unparsed_config)
