FROM python:3.9-slim AS base

FROM base as build
RUN apt -y update &&\ 
    apt-get install -y git &&\
    apt -y install build-essential &&\
    apt-get clean &&\
    pip install -U pip setuptools
COPY . .
RUN mkdir -p /install &&\
    python setup.py bdist_wheel &&\
    python -m pip install --prefix=/install dist/*.whl

FROM base
COPY --from=build /install /usr/local