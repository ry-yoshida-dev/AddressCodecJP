from http import HTTPStatus

from address_codec_jp.errors import (
    AmbiguousAddressError,
    DatasetNotImportedError,
    UnsupportedDatabaseError,
)
from address_codec_jp.frontends.api.database_busy_error import DatabaseBusyError
from address_codec_jp.frontends.api.invalid_request_error import InvalidRequestError


class ErrorStatus:
    """Mapping from the errors of a query to HTTP status codes."""

    def of(self, error: Exception) -> HTTPStatus:
        """
        Choose the status of an error.

        Parameters
        ----------
        error : Exception
            Error raised by a query.

        Returns
        -------
        HTTPStatus
            409 for an ambiguous address, 404 for anything not found, 503 for data not
            prepared on the server or a database locked by another process, 400 for an
            ``InvalidRequestError``, and 500 otherwise, including a library error about
            malformed data.
        """
        match error:
            case AmbiguousAddressError():
                return HTTPStatus.CONFLICT
            case LookupError():
                return HTTPStatus.NOT_FOUND
            case DatasetNotImportedError() | UnsupportedDatabaseError() | DatabaseBusyError():
                return HTTPStatus.SERVICE_UNAVAILABLE
            case InvalidRequestError():
                return HTTPStatus.BAD_REQUEST
            case _:
                return HTTPStatus.INTERNAL_SERVER_ERROR
