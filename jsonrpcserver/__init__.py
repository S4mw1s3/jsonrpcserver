"""Use __all__ so mypy considers these re-exported."""
__all__ = [
    "Error",
    "InvalidParams",
    "Result",
    "Success",
    "async_dispatch",
    "async_dispatch_to_response",
    "async_dispatch_to_serializable",
    "dispatch",
    "dispatch_to_response",
    "dispatch_to_serializable",
    "method",
    "serve",
]


from .async_main import (
    dispatch as async_dispatch,
    dispatch_to_response as async_dispatch_to_response,
    dispatch_to_serializable as async_dispatch_to_serializable,
)
from .main import dispatch, dispatch_to_response, dispatch_to_serializable
from .methods import method
from .result import Error, InvalidParams, Result, Success
from .server import serve as serve
