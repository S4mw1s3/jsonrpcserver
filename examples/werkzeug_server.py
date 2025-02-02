from jsonrpcserver import method, Result, Success, dispatch
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response


@method
def ping() -> Result:
    return Success("pong")


@Request.application
def application(request):
    return Response(dispatch(request.data.decode()), 200, mimetype="application/json")


if __name__ == "__main__":
    run_simple("localhost", 5000, application)
