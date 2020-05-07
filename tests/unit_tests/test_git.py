import requests

import pytest

from automl.processing.git import GitURL
from automl.processing.utils import download_config
from automl.exceptions.automl_exceptions import AutomlGitError

BITBUCKET_ACCESS_TOKEN = "bitbucket_123456"
GITHUB_ACCESS_TOKEN = "github_123456"
GITLAB_ACCESS_TOKEN = "gitlab_123456"
GITLAB_ID = "123456"


@pytest.mark.parametrize(
    "url,token,id,branch,file,repo_url,raw_config_url",
    [
        (
            "https://bitbucket.org/Lombiq/orchard-dojo-library",
            None,
            None,
            "master",
            ".gitignore",
            "https://bitbucket.org/Lombiq/orchard-dojo-library",
            "https://bitbucket.org/Lombiq/orchard-dojo-library/raw/master/.gitignore"
        ),
        (
            "https://gitlab.com/CalcProgrammer1/OpenRGB",
            None,
            None,
            "master",
            ".gitignore",
            "https://gitlab.com/CalcProgrammer1/OpenRGB",
            "https://gitlab.com/CalcProgrammer1/OpenRGB/raw/master/.gitignore"
        ),
        (
            "https://github.com/valeger/automl-example-project",
            None,
            None,
            "master",
            "config.yaml",
            "https://github.com/valeger/automl-example-project",
            "https://raw.githubusercontent.com/valeger/automl-example-project/master/config.yaml"
        ),
        (
            "https://bitbucket.org/valeger/automl",
            f"{BITBUCKET_ACCESS_TOKEN}",
            None,
            "main",
            "config.yaml",
            f"https://valeger:{BITBUCKET_ACCESS_TOKEN}@bitbucket.org/valeger/automl",
            (
                "https://api.bitbucket.org/2.0/repositories/valeger/automl/src/main/config.yaml?access_token="
                f"{BITBUCKET_ACCESS_TOKEN}"
            )
        ),
        (
            "https://gitlab.com/valeger1/automl",
            f"{GITLAB_ACCESS_TOKEN}",
            f"{GITLAB_ID}",
            "main",
            "config.yaml",
            f"https://valeger1:{GITLAB_ACCESS_TOKEN}@gitlab.com/valeger1/automl",
            f"https://gitlab.com/api/v4/projects/{GITLAB_ID}/repository/files/config.yaml/raw?ref=main&private_token={GITLAB_ACCESS_TOKEN}"
        ),
        (
            "https://github.com/valeger/dagster-delta",
            f"{GITHUB_ACCESS_TOKEN}",
            None,
            "master",
            "config.yaml",
            f"https://valeger:{GITHUB_ACCESS_TOKEN}@github.com/valeger/dagster-delta",
            f"https://valeger:{GITHUB_ACCESS_TOKEN}@raw.githubusercontent.com/valeger/dagster-delta/master/config.yaml"
        )
    ]
)
def test_GitURL(url, token, id, branch, file, repo_url, raw_config_url):
    git_object = GitURL(url, token=token, id=id, branch=branch, file=file)
    assert git_object.repo_url == repo_url
    assert git_object.raw_config_url == raw_config_url


@pytest.mark.parametrize(
    "invalid_url",
    [
        "ssh://git@bitbucket.org:Lombiq/orchard-dojo-library.git",
        "git@github.com:dagster-io/dagster.git",
        "https://dev.azure.com/foo/bar"
    ]
)
def test_GitURL_with_errors(invalid_url):
    with pytest.raises(AutomlGitError) as e:
        GitURL(invalid_url)
        assert e


@pytest.mark.parametrize(
    "valid_url",
    [
        "https://bitbucket.org/Lombiq/orchard-dojo-library/raw/master/.gitignore",
        "https://gitlab.com/CalcProgrammer1/OpenRGB/raw/master/.gitignore",
        "https://raw.githubusercontent.com/valeger/automl-example-project/master/config.yaml"
    ]
)
def test_download_config(valid_url):
    try:
        download_config(valid_url)
    except Exception:
        assert False


@pytest.mark.parametrize(
    "invalid_url",
    [
        "https://bitbucket.org/Lombiq/orchard-dojo-library/raw/master",
        "https://gitlab.com/CalcProgrammer1/OpenRGB/raw/master",
        "https://raw.githubusercontent.com/valeger/dagster-delta",
    ]
)
def test_download_config_with_error(invalid_url):
    with pytest.raises(requests.exceptions.HTTPError):
        download_config(invalid_url)
