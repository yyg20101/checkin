from __future__ import annotations

from collections.abc import Callable
from typing import Any

import requests as standard_requests
from curl_cffi import requests as browser_requests
from curl_cffi.requests import exceptions as browser_exceptions


DEFAULT_TIMEOUT_SECONDS = 30
BROWSER_IMPERSONATE = "chrome110"

REQUEST_EXCEPTIONS = (
    standard_requests.RequestException,
    browser_exceptions.RequestException,
)

standard_client = standard_requests
browser_client = browser_requests
SessionFactory = Callable[[], Any]


def standard_session() -> standard_requests.Session:
    return standard_requests.Session()


def browser_session() -> Any:
    return browser_requests.Session()
