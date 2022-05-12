[![GitHub release](https://img.shields.io/github/v/release/valeger/automl.svg)](https://github.com/valeger/automl/releases/latest)
[![CI workflow](https://img.shields.io/github/workflow/status/valeger/automl/ci?label=ci&logo=github&style=flat)](https://github.com/valeger/automl/actions?workflow=ci)
[![codecov](https://codecov.io/gh/valeger/automl/branch/master/graph/badge.svg?token=EMWNQ6FW2S)](https://codecov.io/gh/valeger/automl) 

## About

Automl is a command line tool that provides a quick and simple deployment (orchestration) of machine learning workflow (workflows)
on any kubernetes cluster.
- Define workflows as a sequence of stages.
- Define stages of the workflow where each step in the stage is a Kubernetes pod.
- Run compute intensive jobs for machine learning or data processing and serve model predictions via HTTP as a step.

In simple terms, automl is a simplified version of the Kuberflow Pipeline, but without necessity of ultra steps for installing the tool on the cluster and in-depth knowledge of kubernetes in particular.
All you need is to add a configuration file in the root directory of your project with some descriptions 
without modifying the structure of your project.

This project was written back in 2019 as a project for personal use, when other orchestration tools like Kuberflow Pipeline, Argo Workflows etc. were not omnipresent enough and lack stable versions.

___

* [Install](#install)
* [Usage](#usage)
  * [Configure workflow](#configure-workflow)
  * [Schedule workflow](#schedule-workflow)
  * [Images](#images)
  * [Secrets](#secrets)
  * [ClI](#cli)
  * [Example](#example)

## Install

Automl can be downloaded from PyPI repository via the following command:

```bash
pip install -i https://test.pypi.org/simple/ml-auto-deploy==1.0.0
```

Or alternatively from the github repository:

```bash
pip install git+https://github.com/valeger/automl.git
```

Check your installation by the following command:

```bash
automl --version
```

In case you use minikube, make sure it has been installed (installation instructions is here). 
Start minikube with the latest kubernetes version automl was tested on: 

```bash
minikube start --kubernetes-version=v1.23.3
```
In case you want to try another kuberenets version, keep in mind that automl uses client-python of version `v23.3.0`, so compatible Kubernetes cluster versions can be found [here](https://github.com/kubernetes-client/python#compatibility).

Make sure an ingress addon in enabled:

```bash
minikube addons enable ingress
```

In case you use your own kubernetes cluster:
- make sure the Kubernetes cluster version falls into [compatibility matrix](https://github.com/kubernetes-client/python#compatibility) of client-python version `v23.3.0`
- make sure you use right Kubernetes context:
  ```bash
  kubectl config current-context
  ```
  In case you want to change it:
  ```bash
  kubectl config use-context my-cluster-name
  ```
- if you need your services to be exposed externally, make sure the ingress controller is [configured](https://kubernetes.github.io/ingress-nginx/deploy/) (must be nginx).

## Usage

### Configure workflow

As was stated above, a workflow is a sequence of stages each of which is a set of specific tasks aka steps (training a model, processing data, serving, etc.). Consider the folowwing project structure:

    .
    ├── models/
        ├── requirements.txt
        ├── processing/
            ├── prepare_and_save.py
            └── ...
        ├── train
            ├── train_sarimax.py
            ├── train_xgboost.py
            └── ...
        ├── compare/
            ├── compare_and_save.py
            └── ...
    ├── ml_api/
        ├── app.py
        ├── requirements.txt
        └── ...
    ├── config.yaml

There are two main directories: the `model` one is for trainig, processing, etc., and the ml_api is for model predictions (please note, that you can freely choose another structure of a project).

Then, the configuration file is as follows:

```yaml
version: 1.0.0
stages: 
  processing: 
    - step_name: "prepare-and-save"
      path_to_executable: models/processing/prepare_and_save.py
      dependency_path: models/requirements.txt
      secrets: ["aws-secret"]
      cpu_request: 0.2
      memory_request: 200
      timeout: 30
  train:      
    - step_name: "train-sarimax"
      path_to_executable: models/train/train_sarimax.py
      dependency_path: models/requirements.txt
      secrets: ["aws-secret"]
      envs:
        hash: 123456abcd
      cpu_request: 0.2
      memory_request: 200
      timeout: 60
    - step_name: "train_xgboost"
      path_to_executable: models/train/train_xgboost.py
      dependency_path: models/requirements.txt
      secrets: ["aws-secret"]
      envs:
        HASH: 123456abcd
      cpu_request: 0.2
      memory_request: 200
      timeout: 60
  compare: 
    - step_name: "best-model"
      path_to_executable: models/compare/compare_and_save.py
      dependency_path: models/requirements.txt
      secrets: ["aws-secret"]
      envs:
        HASH: 123456abcd
      cpu_request: 0.2
      memory_request: 200
      timeout: 30
  serve:
    - step_name: "api"
      path_to_executable: ml_api/app.py
      dependency_path: deploy/requirements.txt
      command: ["gunicorn", "-b", ":5000", "ml_api.app:app"]
      secrets: ["aws-secret","db-secret"]
      envs:
        HASH: 123456abcd
      timeout: 30
      min_ready_seconds: 5
      cpu_request: 0.2
      memory_request: 200
      service:
        port: 5000
        ingress: True
```

#### Stage

A stage is a set of steps (tasks) that run parallely. So the main point of one stage is to join some tasks that are independent from each other and thus can be executed in parallel.

In the above example there are 4 stages: processing -> train -> compare -> serve. The `train` stage makes two independant Kubernetes Jobs that train models in parallel.

All stages must be named, and will be renamed if necessary based on [kubernetes names convention](https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#dns-label-names).

#### Step

A step is an independant computing unit in the workflow and can be of two types:

  - a job, without `service` parameter (one pod)
  - a deployment, must be with the `service` parameter (>= 1 replicas)

All the step configuration parameters are listed below.

`step_name` (required)
    
  The name of the step. As was stated above, all invalid names will be fixed according to [convention](https://kubernetes.io/docs/concepts/overview/working-with-objects/names/#dns-label-names).
  
`path_to_executable` (required)
    
  Path to the .py or .ipynb module.

`dependency_path` (required)

  Path to the requirements.txt file.

`image`

  Client docker image repository. There are [several instances](#images) when the defualt image won't be the best solution.  
  If it's your case and if your repo is private, the secret of type=kubernetes.io/dockerconfigjson must be created in advance.  
  Default repo is public.

`command`

  == CMD Dockerfile instruction.

`envs`

  Environment variables to pass to a pod.

`secrets`

  List of the Opaque kubernetes [secrets](#secrets) to bind with a pod. Must be created in advance.

`cpu_request`

  Required amount of CPU resources per container (in cpu units).

`memory_request`

  Required amount of memory per container (withount units, only integer).

`replicas`

  Deployment replicas.

`backoff_limit`

  Kubernetes [.spec.backoffLimit](https://kubernetes.io/docs/concepts/workloads/controllers/job/#pod-backoff-failure-policy) param in Job spec.

`revision_history_limit`

  Kubernetes [.spec.revisionHistoryLimit](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#clean-up-policy) param in Deployment spec.

`timeout`

  Maximum number of seconds to wait for deployment/job completion before calling a custom timeout error.  
  Defaults to 20s.

`polling_time`

  Time between polling (in seconds) of job/deployemnt status (to not overload kube-apiserver with requests).  
  Defaults to 1s.

`wait_before_start_time`

  Time (in seconds) to wait before starting to monitor deployments (to allow deployments to be created, to install packages, etc).

`min_ready_seconds`

  Kubernetes [.spec.minReadySeconds](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#min-ready-seconds) param in Deployment spec.

`service` (required if deployment)

  Configuration for the deployemnt's service. By default, port is 5000, and ingress is turned off.


As soon as configuration file is ready, you can deploy your workflow with auotml [CLI](#cli) tool.  

### Schedule workflow

In case you want to periodically recompute the workflow, use `cronworkflow` (or `cw` alias) command with --schedule option (required):

```bash
automl create cw --schedule=0 12 * * *
```

Keep in mind that cron expression format is a string consisting of **five** fields. Allowed fileds and special characters are listed below.

|     Name     | Allowed values | Allowed Special Characters |
|--------------|----------------|----------------------------|
| Minutes      |     0-59       |, - * /|
| Hours        |     0-23       |, - * /|
| Day of month |     1-31       |, - * /|
| Month        |     0-12       |, - * /|
| Day of week  |     0-6        |, - * /|
  
### Images

All provided packages in requirements.txt will be installed in running docker container (the defualt client image).

You have to provide a custom docker image in the cases listed below:

- The container entrypoint is running as root (UID 0). So, if it's necessary to run container as non-root user, please provide your own image with all installed packages and your project with all necessary changes. You can set/change CMD via `command` parameter in configuration file.
- You need some third-party dependencies that cannot be installed via python package managers, for example jars packages for Spark delta lake, etc.

Note that automl works only with [Docker Hub](https://hub.docker.com/) image repository.

### Secrets

In the case where you need some sensitive information, the best thing to do is to create secrets beforehand which later will be attached to a pod/pods.  For example, suppose that an AWS credentials are necessary to store model checkpoints in an AWS S3 bucket. The===0n, you have to create a Kubernets Secret (Opaque type) with two data fields via automl command:

```bash
automl create secret aws-secret AWS_ACCESS_KEY_ID=123456 AWS_SECRET_ACCESS_KEY=123456
```

In configuration file a `secrets` parameter must be provided with list of the created secrets for a step where sensitive information is required.  
All secrets (i.e. data fields) will be visivle to the pod of the step as environment variables (in the example above AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY).

Note that if you use your custom image and repository is private, a secret of type=kubernetes.io/dockerconfigjson with docker configuration file as `.dockerconfigjson` data field must be created:

```bash
export DOCKER_CONFIG_JSON="$(cat ~/.docker/config.json)" &&\
automl create secret docker .dockerconfigjson=$(echo $DOCKER_CONFIG_JSON) \
--namespace=automl \
--type=kubernetes.io/dockerconfigjson
```

If repository of your project is private, automl will automatically create the secret of name `repo-{name-of-workflow}` with PAT access token as a data field (the PAT access token must be provided as a [CLI option](#secret) if the project repo is private).

### CLI

Automl CLI tool allows you to:

- create
- update 
- delete
- get information about created/running Kubernets recources and their statuses in tabular form
- get logs from Kubernetes jobs in the user-friendly form

for three type of automl abstractions:

- secret
- workflow
- scheduled workflow - cronworkflow

The tables below describes all actions automl commands perform.

#### Secret

| Command         | Arguments    | Options                                           | Descriptions                                |
|-----------------|--------------|---------------------------------------------------|---------------------------------------------|
| `create secret` | name<br>data | --namespace, -ns <br>--type, -t<br>--workflow, -w | Create a secret passing its name as a `name` argument and its data as a `data` argument in the "KEY=value" form.<br> The namespace to put secret in is set by `--namesapce` option.<br> The name of the workflow to bound secret with is set by `--workflow` option.<br>[Type of secret](https://kubernetes.io/docs/concepts/configuration/secret/#secret-types) is set via `--type` option. |
| `update secret` | name<br>data | --namespace, -ns | Update the secret passing its name as a `name` argument and its new data as a `data` argument.<br>If you want to remove a key in the secret, just pass the key with empty string KEY="". |
| `delete secret` | name         | --namespace, -ns | Delete one secret specifying its name and namespace. |
| `get secrets`   | -            | --namespace, -ns | List all secrets in the namespace. |

#### Workflow/cronworkflow

The table below describes `workflow` commands, but also applies to cronworkflow (or cw as alias). Note that in cronworkflow case the `--schedule` option is required as was states [above](#schedule-workflow).

| Command           | Arguments   | Options                                           | Descriptions                                |
|-------------------|-------------|---------------------------------------------------|---------------------------------------------|
| `create workflow` | name<br>url | --namespace, -ns <br>--branch, -b<br>--file, -f<br>--check<br>--token, -t<br>--id | Create a workflow passing its name as a `name` argument and the project url as a `url` argument.<br> Note that currently only github, bitbucket and gitlab project repositories are supported.<br><br>The namespace to create workflow recources in is set by `--namesapce` option.<br>The branch of the project is set by `--branch` option. By default, it's a master branch.<br>The name of the automl configuration file is set by `--file` option (defaults to `config.yaml`). The file must be in the root directory.<br>The check flag if turned on enables an early verification of the configuration file (before some resources are created).<br>In the case your project repository is private, you have to provide a PAT access token by passing it as `--token` option.<br>An `--id` option must be specified only if your project is hosted on gitlab.com and if it's private.<br><br>Guidelines on how to create PAT tokens can be found here: [github](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token), [bitbucket](https://developer.atlassian.com/cloud/bitbucket/rest/intro/), [gitlab](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html).<br>|
| `update workflow` | name<br>url | --namespace, -ns <br>--token, -t<br>--id<br>--branch, -b<br>--file, -f<br>--check | Update workflow passing its name as a `name` argument and the project url as a `url` argument.<br>The purpose of the other options remains the same. |
| `delete workflow` | name        | --namespace, -ns | Delete one workflow and its resources specifying its name and namespace. |
| `get workflow`    | name        | --namespace, -ns<br>--logs | List all resources of the workflow specified by its name in the namespace. Information will be printed in the tabular form.<br>If `--logs` parameter is passed, then instead of resources information logs will be printed.<br><br>Note that logs display useful information about currently ongoing, completed or failed steps of the workflow,<br>and in case they failed, why. So, in cases when it's necessary to read more detailed logs from your python module,<br> run `automl get {name-of-workflow}`, pick-up the name of the job/deployment that interests you<br>(your module will be denoted as `executable_module`) and then run `kubectl logs {name-of-resource}`. |
| `get workflows`   | -           | --namespace, -ns | List names of all actual workflows in the namespace. |

### Example

