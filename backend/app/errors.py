from typing import NoReturn

from fastapi import HTTPException, status


class ServiceNotConfigured(Exception):
    """A required key for a third-party service is missing. Returned as a 503."""


def not_implemented() -> NoReturn:
    raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "Not implemented yet")
