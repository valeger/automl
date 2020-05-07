import typing as t
import os
import sys
import json
import urllib3
import functools
import requests
import traceback

from kubernetes import client, config


class StopWorkflowExecution(Exception):
    """Raise when a specific workflow/cronworkflow cannot be executed"""


class AutomlValueError(ValueError):
    """Raise when a specific subset of values is wrong"""


class AutomlTimeoutError(TimeoutError):
    """Raise when stage timeout is over"""


class AutomlGitError(RuntimeError):
    """Raise when provided git remote url cannot be processed"""


class AutomlOSError(OSError):
    """Raise when file extensions are not supported"""


def exception_handler(
    f: t.Callable[..., t.Any] = None, *, logger
) -> t.Callable[..., t.Callable]:
    """Decorator for handling all possible errors via logging.

    :param logger: Logger object to pass.
    """
    if f is None:
        return functools.partial(exception_handler, logger=logger)

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            f(*args, **kwargs)

        except config.ConfigException:
            _, value, tb = sys.exc_info()
            if os.getenv("KUBERNETES_SERVICE_HOST"):
                logger.error(
                    f"Cannot find credentials for authorization in a runner: {value} \n"
                    "Traceback: \n"
                    + "\n".join(traceback.format_tb(tb)[2:])
                )
            else:
                logger.error(
                    f"Cannot find token from kubeconfig file for authorization: {value} \n"
                    "Traceback: \n"
                    + "\n".join(traceback.format_tb(tb)[2:])
                )

        except urllib3.exceptions.MaxRetryError:
            _, value, tb = sys.exc_info()
            logger.error(
                f"Cannot connect to Kubernetes API: {value.url}\n"  # type: ignore
                "Traceback: \n"
                + "\n".join(traceback.format_tb(tb)[2:])
            )
        except client.ApiException:
            _, value, tb = sys.exc_info()
            message = (
                json.loads(value.body)["message"]   # type: ignore
                if value.body else None             # type: ignore
            )
            logger.error(
                f"Kubernetes API error (code {value.status}): {message}\n"  # type: ignore
                "Traceback: \n"
                + "\n".join(traceback.format_tb(tb)[2:])
            )
        except (
            AutomlOSError,
            AutomlGitError,
            AutomlValueError,
            requests.HTTPError,
            AutomlTimeoutError,
            StopWorkflowExecution
        ) as e:
            logger.error(e)

        except Exception as e:
            logger.error(f"Unpredicted error has occured: {e}", exc_info=1)

    return wrapper
