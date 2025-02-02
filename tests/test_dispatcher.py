"""TODO: Add tests for dispatch_requests (non-pure version)"""
from typing import Any
from unittest.mock import patch, sentinel
import json
import pytest

from oslash.either import Left, Right

from jsonrpcserver.codes import (
    ERROR_INTERNAL_ERROR,
    ERROR_INVALID_PARAMS,
    ERROR_INVALID_REQUEST,
    ERROR_METHOD_NOT_FOUND,
    ERROR_PARSE_ERROR,
    ERROR_SERVER_ERROR,
)
from jsonrpcserver.dispatcher import (
    call,
    create_request,
    dispatch_deserialized,
    dispatch_request,
    dispatch_to_response_pure,
    extract_list,
    extract_args,
    extract_kwargs,
    get_method,
    not_notification,
    to_response,
    validate_args,
    validate_request,
)
from jsonrpcserver.exceptions import JsonRpcError
from jsonrpcserver.main import (
    default_deserializer,
    default_validator,
    dispatch_to_response,
)
from jsonrpcserver.methods import method
from jsonrpcserver.request import Request
from jsonrpcserver.response import ErrorResponse, SuccessResponse
from jsonrpcserver.result import (
    ErrorResult,
    InvalidParams,
    Result,
    Success,
    SuccessResult,
    NODATA,
)
from jsonrpcserver.sentinels import NOCONTEXT, NOID
from jsonrpcserver.utils import identity


def ping() -> Result:
    return Success("pong")


# extract_list


def test_extract_list():
    assert extract_list(False, [SuccessResponse("foo", 1)]) == SuccessResponse("foo", 1)


def test_extract_list_notification():
    assert extract_list(False, [None]) == None


def test_extract_list_batch():
    assert extract_list(True, [SuccessResponse("foo", 1)]) == [
        SuccessResponse("foo", 1)
    ]


def test_extract_list_batch_all_notifications():
    assert extract_list(True, []) == None


# to_response


def test_to_response_SuccessResult():
    assert to_response(
        Request("ping", [], sentinel.id), Right(SuccessResult(sentinel.result))
    ) == Right(SuccessResponse(sentinel.result, sentinel.id))


def test_to_response_ErrorResult():
    assert (
        to_response(
            Request("ping", [], sentinel.id),
            Left(
                ErrorResult(
                    code=sentinel.code, message=sentinel.message, data=sentinel.data
                )
            ),
        )
    ) == Left(
        ErrorResponse(sentinel.code, sentinel.message, sentinel.data, sentinel.id)
    )


def test_to_response_InvalidParams():
    assert to_response(
        Request("ping", [], sentinel.id), InvalidParams(sentinel.data)
    ) == Left(ErrorResponse(-32602, "Invalid params", sentinel.data, sentinel.id))


def test_to_response_InvalidParams_no_data():
    assert to_response(Request("ping", [], sentinel.id), InvalidParams()) == Left(
        ErrorResponse(-32602, "Invalid params", NODATA, sentinel.id)
    )


def test_to_response_notification():
    with pytest.raises(AssertionError):
        to_response(Request("ping", [], NOID), SuccessResult(result=sentinel.result))


# extract_args


def test_extract_args():
    assert extract_args(Request("ping", [], NOID), NOCONTEXT) == []


def test_extract_args_with_context():
    assert extract_args(Request("ping", ["bar"], NOID), "foo") == ["foo", "bar"]


# extract_kwargs


def test_extract_kwargs():
    assert extract_kwargs(Request("ping", {"foo": "bar"}, NOID)) == {"foo": "bar"}


# validate_result


def test_validate_result_no_arguments():
    f = lambda: None
    assert validate_args(Request("f", [], NOID), NOCONTEXT, f) == Right(f)


def test_validate_result_no_arguments_too_many_positionals():
    assert validate_args(Request("f", ["foo"], NOID), NOCONTEXT, lambda: None) == Left(
        ErrorResult(
            code=ERROR_INVALID_PARAMS,
            message="Invalid params",
            data="too many positional arguments",
        )
    )


def test_validate_result_positionals():
    f = lambda x: None
    assert validate_args(Request("f", [1], NOID), NOCONTEXT, f) == Right(f)


def test_validate_result_positionals_not_passed():
    assert validate_args(
        Request("f", {"foo": "bar"}, NOID), NOCONTEXT, lambda x: None
    ) == Left(
        ErrorResult(
            ERROR_INVALID_PARAMS, "Invalid params", "missing a required argument: 'x'"
        )
    )


def test_validate_result_keywords():
    f = lambda **kwargs: None
    assert validate_args(Request("f", {"foo": "bar"}, NOID), NOCONTEXT, f) == Right(f)


def test_validate_result_object_method():
    class FooClass:
        def foo(self, one, two):
            return "bar"

    f = FooClass().foo
    assert validate_args(Request("f", ["one", "two"], NOID), NOCONTEXT, f) == Right(f)


# call


def test_call():
    assert call(Request("ping", [], 1), NOCONTEXT, ping) == Right(SuccessResult("pong"))


def test_call_raising_jsonrpcerror():
    def method():
        raise JsonRpcError(code=1, message="foo", data=NODATA)

    assert call(Request("ping", [], 1), NOCONTEXT, method) == Left(
        ErrorResult(1, "foo")
    )


def test_call_raising_exception():
    def method():
        raise ValueError("foo")

    assert call(Request("ping", [], 1), NOCONTEXT, method) == Left(
        ErrorResult(ERROR_INTERNAL_ERROR, "Internal error", "foo")
    )


# validate_args


def test_validate_args():
    assert validate_args(Request("ping", [], 1), NOCONTEXT, ping) == Right(ping)


def test_validate_args():
    assert validate_args(Request("ping", ["foo"], 1), NOCONTEXT, ping) == Left(
        ErrorResult(
            ERROR_INVALID_PARAMS, "Invalid params", "too many positional arguments"
        )
    )


# get_method


def test_get_method():
    assert get_method({"ping": ping}, "ping") == Right(ping)


def test_get_method():
    assert get_method({"ping": ping}, "non-existant") == Left(
        ErrorResult(ERROR_METHOD_NOT_FOUND, "Method not found", "non-existant")
    )


# dispatch_request


def test_dispatch_request():
    request = Request("ping", [], 1)
    assert dispatch_request({"ping": ping}, NOCONTEXT, request) == (
        request,
        Right(SuccessResult("pong")),
    )


def test_dispatch_request_with_context():
    def ping_with_context(context: Any):
        assert context is sentinel.context
        return Success()

    dispatch_request(
        {"ping_with_context": ping_with_context},
        sentinel.context,
        Request("ping_with_context", [], 1),
    )
    # Assert is in the method


# create_request


def test_create_request():
    request = create_request({"jsonrpc": "2.0", "method": "ping"})
    assert isinstance(request, Request)


# not_notification


def test_not_notification():
    assert not_notification((Request("ping", [], 1), SuccessResult("pong"))) == True


def test_not_notification_false():
    assert not_notification((Request("ping", [], NOID), SuccessResult("pong"))) == False


# dispatch_deserialized


def test_dispatch_deserialized():
    assert (
        dispatch_deserialized(
            methods={"ping": ping},
            context=NOCONTEXT,
            post_process=identity,
            deserialized={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )
        == Right(SuccessResponse("pong", 1))
    )


# validate_request


def test_validate_request():
    request = {"jsonrpc": "2.0", "method": "ping"}
    assert validate_request(default_validator, request) == Right(request)


def test_validate_request_invalid():
    assert validate_request(default_validator, {"jsonrpc": "2.0"}) == Left(
        ErrorResponse(
            ERROR_INVALID_REQUEST,
            "Invalid request",
            "The request failed schema validation",
            None,
        )
    )


# dispatch_request


def test_dispatch_request():
    request = Request("ping", [], 1)
    assert dispatch_request({"ping": ping}, NOCONTEXT, request) == (
        request,
        Right(SuccessResult("pong")),
    )


# dispatch_to_response_pure


def test_dispatch_to_response_pure():
    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"ping": ping},
            request='{"jsonrpc": "2.0", "method": "ping", "id": 1}',
        )
        == Right(SuccessResponse("pong", 1))
    )


def test_dispatch_to_response_pure_parse_error():
    """Unable to parse, must return an error"""
    assert dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods={"ping": ping},
        request="{",
    ) == Left(
        ErrorResponse(
            ERROR_PARSE_ERROR,
            "Parse error",
            "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
            None,
        )
    )


def test_dispatch_to_response_pure_invalid_request():
    """Invalid JSON-RPC, must return an error. (impossible to determine if
    notification).
    """
    assert dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods={"ping": ping},
        request="{}",
    ) == Left(
        ErrorResponse(
            ERROR_INVALID_REQUEST,
            "Invalid request",
            "The request failed schema validation",
            None,
        )
    )


def test_dispatch_to_response_pure_method_not_found():
    assert dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods={},
        request='{"jsonrpc": "2.0", "method": "non_existant", "id": 1}',
    ) == Left(
        ErrorResponse(ERROR_METHOD_NOT_FOUND, "Method not found", "non_existant", 1)
    )


def test_dispatch_to_response_pure_invalid_params_auto():
    def foo(colour: str, size: str):
        return Success()

    assert dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods={"foo": foo},
        request='{"jsonrpc": "2.0", "method": "foo", "params": {"colour":"blue"}, "id": 1}',
    ) == Left(
        ErrorResponse(
            ERROR_INVALID_PARAMS,
            "Invalid params",
            "missing a required argument: 'size'",
            1,
        )
    )


def test_dispatch_to_response_pure_invalid_params_explicitly_returned():
    def foo(colour: str) -> Result:
        if colour not in ("orange", "red", "yellow"):
            return InvalidParams()

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"foo": foo},
            request='{"jsonrpc": "2.0", "method": "foo", "params": ["blue"], "id": 1}',
        )
        == Left(ErrorResponse(ERROR_INVALID_PARAMS, "Invalid params", NODATA, 1))
    )


def test_dispatch_to_response_pure_internal_error():
    def foo():
        raise ValueError("foo")

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"foo": foo},
            request='{"jsonrpc": "2.0", "method": "foo", "id": 1}',
        )
        == Left(ErrorResponse(ERROR_INTERNAL_ERROR, "Internal error", "foo", 1))
    )


@patch("jsonrpcserver.dispatcher.dispatch_request", side_effect=ValueError("foo"))
def test_dispatch_to_response_pure_server_error(*_):
    def foo():
        return Success()

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"foo": foo},
            request='{"jsonrpc": "2.0", "method": "foo", "id": 1}',
        )
        == Left(ErrorResponse(ERROR_SERVER_ERROR, "Server error", "foo", None))
    )


def test_dispatch_to_response_pure_invalid_result():
    """Methods should return a Result, otherwise we get an Internal Error response."""

    def not_a_result():
        return None

    assert dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods={"not_a_result": not_a_result},
        request='{"jsonrpc": "2.0", "method": "not_a_result", "id": 1}',
    ) == Left(
        ErrorResponse(
            ERROR_INTERNAL_ERROR,
            "Internal error",
            "The method did not return a valid Result (returned None)",
            1,
        )
    )


def test_dispatch_to_response_pure_raising_exception():
    """Allow raising an exception to return an error."""

    def raise_exception():
        raise JsonRpcError(code=0, message="foo", data="bar")

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"raise_exception": raise_exception},
            request='{"jsonrpc": "2.0", "method": "raise_exception", "id": 1}',
        )
        == Left(ErrorResponse(0, "foo", "bar", 1))
    )


# dispatch_to_response_pure -- Notifications


def test_dispatch_to_response_pure_notification():
    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"ping": ping},
            request='{"jsonrpc": "2.0", "method": "ping"}',
        )
        == None
    )


def test_dispatch_to_response_pure_notification_parse_error():
    """Unable to parse, must return an error"""
    assert dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods={"ping": ping},
        request="{",
    ) == Left(
        ErrorResponse(
            ERROR_PARSE_ERROR,
            "Parse error",
            "Expecting property name enclosed in double quotes: line 1 column 2 (char 1)",
            None,
        )
    )


def test_dispatch_to_response_pure_notification_invalid_request():
    """Invalid JSON-RPC, must return an error. (impossible to determine if notification)"""
    assert dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods={"ping": ping},
        request="{}",
    ) == Left(
        ErrorResponse(
            ERROR_INVALID_REQUEST,
            "Invalid request",
            "The request failed schema validation",
            None,
        )
    )


def test_dispatch_to_response_pure_notification_method_not_found():
    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={},
            request='{"jsonrpc": "2.0", "method": "non_existant"}',
        )
        == None
    )


def test_dispatch_to_response_pure_notification_invalid_params_auto():
    def foo(colour: str, size: str):
        return Success()

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"foo": foo},
            request='{"jsonrpc": "2.0", "method": "foo", "params": {"colour":"blue"}}',
        )
        == None
    )


def test_dispatch_to_response_pure_invalid_params_notification_explicitly_returned():
    def foo(colour: str) -> Result:
        if colour not in ("orange", "red", "yellow"):
            return InvalidParams()

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"foo": foo},
            request='{"jsonrpc": "2.0", "method": "foo", "params": ["blue"]}',
        )
        == None
    )


def test_dispatch_to_response_pure_notification_internal_error():
    def foo(bar):
        raise ValueError

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"foo": foo},
            request='{"jsonrpc": "2.0", "method": "foo"}',
        )
        == None
    )


@patch("jsonrpcserver.dispatcher.dispatch_request", side_effect=ValueError("foo"))
def test_dispatch_to_response_pure_notification_server_error(*_):
    def foo():
        return Success()

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"foo": foo},
            request='{"jsonrpc": "2.0", "method": "foo"}',
        )
        == Left(ErrorResponse(ERROR_SERVER_ERROR, "Server error", "foo", None))
    )


def test_dispatch_to_response_pure_notification_invalid_result():
    """Methods should return a Result, otherwise we get an Internal Error response."""

    def not_a_result():
        return None

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"not_a_result": not_a_result},
            request='{"jsonrpc": "2.0", "method": "not_a_result"}',
        )
        == None
    )


def test_dispatch_to_response_pure_notification_raising_exception():
    """Allow raising an exception to return an error."""

    def raise_exception():
        raise JsonRpcError(code=0, message="foo", data="bar")

    assert (
        dispatch_to_response_pure(
            deserializer=default_deserializer,
            validator=default_validator,
            post_process=identity,
            context=NOCONTEXT,
            methods={"raise_exception": raise_exception},
            request='{"jsonrpc": "2.0", "method": "raise_exception"}',
        )
        == None
    )


# dispatch_to_response


def test_dispatch_to_response():
    response = dispatch_to_response(
        '{"jsonrpc": "2.0", "method": "ping", "id": 1}', {"ping": ping}
    )
    assert response == Right(SuccessResponse("pong", 1))


def test_dispatch_to_response_with_global_methods():
    @method
    def ping():
        return Success("pong")

    response = dispatch_to_response('{"jsonrpc": "2.0", "method": "ping", "id": 1}')
    assert response == Right(SuccessResponse("pong", 1))


# The remaining tests are direct from the examples in the specification


def test_examples_positionals():
    def subtract(minuend, subtrahend):
        return Success(minuend - subtrahend)

    response = dispatch_to_response_pure(
        methods={"subtract": subtract},
        context=NOCONTEXT,
        validator=default_validator,
        post_process=identity,
        deserializer=default_deserializer,
        request='{"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 1}',
    )
    assert response == Right(SuccessResponse(19, 1))

    # Second example
    response = dispatch_to_response_pure(
        methods={"subtract": subtract},
        context=NOCONTEXT,
        validator=default_validator,
        post_process=identity,
        deserializer=default_deserializer,
        request='{"jsonrpc": "2.0", "method": "subtract", "params": [23, 42], "id": 2}',
    )
    assert response == Right(SuccessResponse(-19, 2))


def test_examples_nameds():
    def subtract(**kwargs):
        return Success(kwargs["minuend"] - kwargs["subtrahend"])

    response = dispatch_to_response_pure(
        methods={"subtract": subtract},
        context=NOCONTEXT,
        validator=default_validator,
        post_process=identity,
        deserializer=default_deserializer,
        request='{"jsonrpc": "2.0", "method": "subtract", "params": {"subtrahend": 23, "minuend": 42}, "id": 3}',
    )
    assert response == Right(SuccessResponse(19, 3))

    # Second example
    response = dispatch_to_response_pure(
        methods={"subtract": subtract},
        context=NOCONTEXT,
        validator=default_validator,
        post_process=identity,
        deserializer=default_deserializer,
        request='{"jsonrpc": "2.0", "method": "subtract", "params": {"minuend": 42, "subtrahend": 23}, "id": 4}',
    )
    assert response == Right(SuccessResponse(19, 4))


def test_examples_notification():
    response = dispatch_to_response_pure(
        methods={"update": lambda: None, "foobar": lambda: None},
        context=NOCONTEXT,
        validator=default_validator,
        post_process=identity,
        deserializer=default_deserializer,
        request='{"jsonrpc": "2.0", "method": "update", "params": [1, 2, 3, 4, 5]}',
    )
    assert response is None

    # Second example
    response = dispatch_to_response_pure(
        methods={"update": lambda: None, "foobar": lambda: None},
        context=NOCONTEXT,
        validator=default_validator,
        post_process=identity,
        deserializer=default_deserializer,
        request='{"jsonrpc": "2.0", "method": "foobar"}',
    )
    assert response is None


def test_examples_invalid_json():
    response = dispatch_to_response_pure(
        methods={"ping": ping},
        context=NOCONTEXT,
        validator=default_validator,
        post_process=identity,
        deserializer=default_deserializer,
        request='[{"jsonrpc": "2.0", "method": "sum", "params": [1,2,4], "id": "1"}, {"jsonrpc": "2.0", "method"]',
    )
    assert response == Left(
        ErrorResponse(
            ERROR_PARSE_ERROR,
            "Parse error",
            "Expecting ':' delimiter: line 1 column 96 (char 95)",
            None,
        )
    )


def test_examples_empty_array():
    # This is an invalid JSON-RPC request, should return an error.
    response = dispatch_to_response_pure(
        request="[]",
        methods={"ping": ping},
        context=NOCONTEXT,
        validator=default_validator,
        post_process=identity,
        deserializer=default_deserializer,
    )
    assert response == Left(
        ErrorResponse(
            ERROR_INVALID_REQUEST,
            "Invalid request",
            "The request failed schema validation",
            None,
        )
    )


def test_examples_invalid_jsonrpc_batch():
    """
    We break the spec here, by not validating each request in the batch individually.
    The examples are expecting a batch response full of error responses.
    """
    response = dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods={"ping": ping},
        request="[1]",
    )
    assert response == Left(
        ErrorResponse(
            ERROR_INVALID_REQUEST,
            "Invalid request",
            "The request failed schema validation",
            None,
        )
    )


def test_examples_multiple_invalid_jsonrpc():
    """
    We break the spec here, by not validating each request in the batch individually.
    The examples are expecting a batch response full of error responses.
    """
    response = dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods={"ping": ping},
        request="[1, 2, 3]",
    )
    assert response == Left(
        ErrorResponse(
            ERROR_INVALID_REQUEST,
            "Invalid request",
            "The request failed schema validation",
            None,
        )
    )


def test_examples_mixed_requests_and_notifications():
    """
    We break the spec here. The examples put an invalid jsonrpc request in the
    mix here.  but it's removed to test the rest, because we're not validating
    each request individually. Any invalid jsonrpc will respond with a single
    error message.

    The spec example includes this which invalidates the entire request:
        {"foo": "boo"},
    """
    methods = {
        "sum": lambda *args: Right(SuccessResult(sum(args))),
        "notify_hello": lambda *args: Right(SuccessResult(19)),
        "subtract": lambda *args: Right(SuccessResult(args[0] - sum(args[1:]))),
        "get_data": lambda: Right(SuccessResult(["hello", 5])),
    }
    requests = json.dumps(
        [
            {"jsonrpc": "2.0", "method": "sum", "params": [1, 2, 4], "id": "1"},
            {"jsonrpc": "2.0", "method": "notify_hello", "params": [7]},
            {"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": "2"},
            {
                "jsonrpc": "2.0",
                "method": "foo.get",
                "params": {"name": "myself"},
                "id": "5",
            },
            {"jsonrpc": "2.0", "method": "get_data", "id": "9"},
        ]
    )
    response = dispatch_to_response_pure(
        deserializer=default_deserializer,
        validator=default_validator,
        post_process=identity,
        context=NOCONTEXT,
        methods=methods,
        request=requests,
    )
    expected = [
        Right(
            SuccessResponse(result=7, id="1")
        ),  # {"jsonrpc": "2.0", "result": 7, "id": "1"},
        Right(
            SuccessResponse(result=19, id="2")
        ),  # {"jsonrpc": "2.0", "result": 19, "id": "2"},
        Left(
            ErrorResponse(
                code=-32601, message="Method not found", data="foo.get", id="5"
            )
        ),
        # {
        #     "jsonrpc": "2.0",
        #     "error": {"code": -32601, "message": "Method not found", "data": "foo.get"},
        #     "id": "5",
        # },
        Right(
            SuccessResponse(result=["hello", 5], id="9")
        ),  # {"jsonrpc": "2.0", "result": ["hello", 5], "id": "9"},
    ]
    # assert isinstance(response, Iterable)
    for r in response:
        assert r in expected
