from typing import cast

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from address_codec_jp.frontends.api.request_too_large_error import RequestTooLargeError
from address_codec_jp.frontends.serialization import ErrorSerializer


class RequestSizeLimit:
    """
    ASGI middleware that rejects a request body larger than a limit before it is parsed.

    A body whose ``Content-Length`` exceeds the limit is rejected without being read.
    Any other body is read up to the limit, so that a body sent in chunks is rejected
    as soon as it grows beyond it, and then handed to the application. A rejected
    request is answered with 413 and the error body of ``RequestTooLargeError``.

    Parameters
    ----------
    app : ASGIApp
        Application that handles the requests within the limit.
    max_bytes : int
        Largest accepted body in bytes.

    Raises
    ------
    ValueError
        If ``max_bytes`` is not positive.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        if max_bytes <= 0:
            raise ValueError(f"max_bytes must be positive, got {max_bytes}.")
        self._app: ASGIApp = app
        self._max_bytes: int = max_bytes
        self._error_serializer: ErrorSerializer = ErrorSerializer()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """
        Handle a connection, checking the size of an HTTP request body.

        Parameters
        ----------
        scope : Scope
            Connection scope.
        receive : Receive
            Channel of the incoming messages.
        send : Send
            Channel of the outgoing messages.
        """
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared_length = Headers(scope=scope).get("content-length", "")
        if declared_length.isdigit() and int(declared_length) > self._max_bytes:
            await self._reject(scope, receive, send)
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                await self._app(scope, self._replay(message, receive), send)
                return
            body = cast(object, message.get("body", b""))
            chunk = body if isinstance(body, bytes) else b""
            size += len(chunk)
            if size > self._max_bytes:
                await self._reject(scope, receive, send)
                return
            chunks.append(chunk)
            more_body = cast(object, message.get("more_body", False))
            if more_body is not True:
                break
        body_message: Message = {"type": "http.request", "body": b"".join(chunks)}
        await self._app(scope, self._replay(body_message, receive), send)

    def _replay(self, first_message: Message, receive: Receive) -> Receive:
        pending: list[Message] = [first_message]

        async def replay() -> Message:
            if pending:
                return pending.pop()
            return await receive()

        return replay

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        error = RequestTooLargeError(f"A request body takes at most {self._max_bytes} bytes.")
        response = JSONResponse(self._error_serializer.serialize(error), status_code=413)
        await response(scope, receive, send)
