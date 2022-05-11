from typing import Dict
from pathlib import Path
from setuptools import find_packages, setup

NAME = "ml-auto-deploy"
DESCRIPTION = "A CLI tool for a ML workflow deployment on Kubernetes cluster"
LONG_DESCRIPTION = DESCRIPTION
URL = "https://github.com/valeger/automl"
EMAIL = "valeger@protonmail.com"
AUTHOR = "valeger"
REQUIRES_PYTHON = ">=3.8.*"


def get_version() -> str:
    version: Dict[str, str] = {}
    ROOT_DIR = Path(__file__).parent.resolve()
    PACKAGE_DIR = ROOT_DIR / 'automl'
    with open(PACKAGE_DIR / "version.py") as f:
        exec(f.read(), version)

    return version["VERSION"]


setup(
    name=NAME,
    version=get_version(),
    author=AUTHOR,
    author_email=EMAIL,
    description=DESCRIPTION,
    long_description=LONG_DESCRIPTION,
    long_description_content_type="text/markdown",
    license="BSD-3",
    python_requires=REQUIRES_PYTHON,
    url=URL,
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: BSD License",
    ],
    packages=find_packages(exclude=["tests.*", "tests"]),
    package_data={
        "automl": ["logger.conf"]
    },
    install_requires=[
        "kubernetes==23.3.0",
        "requests",
        "PyYAML",
        "click>=7.1.2",
        "pydantic==1.9.0",
        "tabulate==0.8.9",
        "colorlog==6.6.0"
    ],
    extras_require={
        "test": [
            "pytest==7.1.2",
            "pytest-cov",
            "mypy",
            "flake8==4.0.1",
            "tox"
        ]
    },
    entry_points={'console_scripts': ['automl = automl.cli:main']}
)
