from address_codec_jp.frontends.api.invalid_request_error import InvalidRequestError


class RequestTooLargeError(InvalidRequestError):
    """Error of a request whose body exceeds the size limit of the service, answered with 413."""
