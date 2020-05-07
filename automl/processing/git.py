import re

from automl.exceptions import AutomlGitError

ALLOWED_REPO_HOSTS = ["github.com", "gitlab.com", "bitbucket.org"]
PROTOCOL = "https"
RAW_GITHUB = "raw.githubusercontent.com"
RAW_GITLAB = (
    "https://gitlab.com/api/v4/projects/{id}/repository/files/"
    "{file}/raw?ref={branch}&private_token={token}"
)
RAW_BITBUCKET = (
    "https://api.bitbucket.org/2.0/repositories/"
    "{username}/{project}/src/{branch}/{file}?access_token={token}"
)
RE_URL = re.compile(
    r"(?:@|\/\/)([\w.-]+)\/([\w._-]+)\/([\w._-]+).*$"
)


class GitURL:

    def __init__(
        self,
        url: str,
        token: str = None,
        id: str = None,
        branch: str = "master",
        file: str = "config.yaml"
    ):
        if not re.match("^https://", url):
            raise AutomlGitError(
                "Error in git connection protocol: only https protocol is supported. "
                f"Url: {url}. "
                "If you're planning to deploy private repo, "
                "please use https protocol and provide PAT token"
            )

        self.url = url
        self.token = token
        self.id = id
        self.branch = branch
        self.file = file
        self.repo = str()
        self.username = str()
        self.project = str()

        if self.token:
            self._validate_token()

        self._fetch_info_from_url()

    @property
    def repo_url(self) -> str:

        if self.token:
            return (
                f"{PROTOCOL}://{self.username}:{self.token}"
                f"@{self.repo}/{self.username}/{self.project}"
            )

        return (
            f"{PROTOCOL}://{self.repo}/{self.username}/{self.project}"
        )

    @property
    def raw_config_url(self) -> str:
        suffix = "raw/"
        repo = self.repo

        if "github" in self.repo:
            suffix = ""
            repo = RAW_GITHUB

        if self.token:
            if "github" in self.repo:
                return (
                    f"{PROTOCOL}://{self.username}:{self.token}"
                    f"@{repo}/{self.username}/{self.project}/"
                    f"{suffix}{self.branch}/{self.file}"
                )

            elif "gitlab" in self.repo:
                if not self.id:
                    raise AutomlGitError(
                        "Please provide correct id of the gitlab project."
                    )
                return RAW_GITLAB.format(
                    id=self.id, file=self.file, branch=self.branch, token=self.token
                )

            elif "bitbucket" in self.repo:
                return RAW_BITBUCKET.format(
                    username=self.username, project=self.project,
                    branch=self.branch, file=self.file, token=self.token
                )

        return (
            f"{PROTOCOL}://{repo}/{self.username}/"
            f"{self.project}/{suffix}{self.branch}/{self.file}"
        )

    def _validate_token(self) -> None:
        self.token = re.sub(r"\/", "%2F", self.token)

    def _fetch_info_from_url(self) -> None:
        try:
            self.repo, self.username, \
                self.project = RE_URL.findall(self.url)[0]
        except IndexError as e:
            raise AutomlGitError(f"Invalid git url: {self.url}") from e

        if self.repo not in ALLOWED_REPO_HOSTS:
            raise AutomlGitError(
                "Automl supports only github, gitlab and bitbucket repositories"
            )

        self.project = re.sub(r".git$", "", self.project)
