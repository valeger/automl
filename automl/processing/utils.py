from typing import Tuple, Dict
import re
import requests

from automl.exceptions import AutomlValueError

RE_K8S_NAME = re.compile(r"[^a-zA-Z0-9.]+")
RE_CRON_MIN = re.compile(
    r"^([1-5]?[0-9](,|$))+"
    r"|^(\*|[1-5]?[0-9]-[1-5]?[0-9])(\/[1-5]?[0-9]$|$)"
)
RE_CRON_HOUR = re.compile(
    r"^((2[0-3]|1?[0-9])(,|$))+"
    r"|^(\*|(2[0-3]|1?[0-9])-(2[0-3]|1?[0-9]))(\/(2[0-3]|1?[0-9])$|$)"
)
RE_CRON_DAY = re.compile(
    r"^((3[0-1]|[1-2]?[0-9])(,|$))+"
    r"|^(\*|(3[0-1]|[1-2]?[0-9])-(3[0-1]|[1-2]?[0-9]))(\/(3[0-1]|[1-2]?[0-9])$|$)"
)
RE_CRON_MONTH = re.compile(
    r"^((1[0-2]|[0-9])(,|$))+"
    r"|^(\*|(1[0-2]|[0-9])-(1[0-2]|[0-9]))(\/(1[0-2]|[0-9])$|$)"
)
RE_CRON_WEEKDAY = re.compile(
    r"^([0-6](,|$))+" r"|^(\*|[0-6]-[0-6])(\/[0-6]$|$)"
)


def fix_k8s_name(name: str) -> str:
    """Remove invalid characters from k8s resource name.

    :param name: Initial name.

    :return: Valid Kubernetes DNS name (RFC 1123).
    """
    return re.sub(r"[^a-z0-9.]+", "-", name.lower().strip()).strip("-")


def validate_schedule(schedule: str) -> str:
    """Validate provided schedule of the cronjob.

    :param schedule: Schedule to validate (minute, hour, day, month, year schema).

    :return: Valid schedule expression.

    :raises automl.exceptions.AutomlValueError: If schedule expression is invalid.
    """
    parsed_schedule = [e for e in schedule.split(" ")]
    if len(parsed_schedule) != 5:
        raise AutomlValueError(
            f"""Incoreect schedule (cron) schema: {schedule}.
            Must have 5 schedule fields"""
        )

    minutes_pattern_matches = RE_CRON_MIN.fullmatch(parsed_schedule[0])
    if minutes_pattern_matches is None:
        raise AutomlValueError(
            f"""Incoreect schedule (cron) schema: {schedule}.
            Incoreect minute pattern: {schedule}"""
        )

    hours_pattern_matches = RE_CRON_HOUR.fullmatch(parsed_schedule[1])
    if hours_pattern_matches is None:
        raise AutomlValueError(
            f"""Incoreect schedule (cron) schema: {schedule}.
            Incorrect hour pattern: {schedule}"""
        )

    day_of_the_month_pattern_matches = RE_CRON_DAY.fullmatch(
        parsed_schedule[2]
    )
    if day_of_the_month_pattern_matches is None:
        raise AutomlValueError(
            f"""Incoreect schedule (cron) schema: {schedule}.
            Incorrect day pattern: {schedule}"""
        )

    month_pattern_matches = RE_CRON_MONTH.fullmatch(parsed_schedule[3])
    if month_pattern_matches is None:
        raise AutomlValueError(
            f"""Incoreect schedule (cron) schema: {schedule}.
            Incorrect month pattern: {schedule}"""
        )

    day_of_week_pattern_matches = RE_CRON_WEEKDAY.fullmatch(
        parsed_schedule[4]
    )
    if day_of_week_pattern_matches is None:
        raise AutomlValueError(
            f"""Incoreect schedule (cron) schema: {schedule}.
            Incorrect weekday pattern: {schedule}"""
        )

    return schedule


def download_config(url: str) -> bytes:
    """Download configuration yaml file from repo.

    :param url: Raw config url.

    :return: config bytestring.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.HTTPError as e:
        if response.status_code in [404, 401]:
            raise requests.HTTPError(
                f"Cannot fetch configuration file from {url}. "
                "Make sure you provide PAT token in case your repo is private."
            ) from e
        else:
            raise requests.HTTPError(
                f"Cannot fetch configuration file from {url} repo. "
                f"Status code: {response.status_code}"
            ) from e
    return response.content


def parse_secrets(unparsed_secrets: Tuple[str]) -> Dict[str, str]:
    """Parse CLI secrets input.

    :param unparsed_secrets: Tuple of the key-value pairs in the "KEY=value" form.

    :return: Dictionary of the parsed key-value pairs.
    """
    parsed_secrets = {}
    for secret in unparsed_secrets:
        sign_index = secret.find("=")

        if sign_index == -1:
            raise AutomlValueError("Secrets must be in the KEY=value form")

        key, value = secret[:sign_index], secret[(sign_index + 1):]

        if not key:
            raise AutomlValueError("Secrets must be in KEY=value form")

        parsed_secrets[key] = value
    return parsed_secrets
