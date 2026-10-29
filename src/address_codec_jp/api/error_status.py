from http import HTTPStatus

from address_codec_jp.api.invalid_request_error import InvalidRequestError
from address_codec_jp.errors.ambiguous_address_error import AmbiguousAddressError
from address_codec_jp.errors.dataset_not_imported_error import DatasetNotImportedError
from address_codec_jp.errors.unsupported_database_error import UnsupportedDatabaseError


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
            prepared on the server, 400 for an ``InvalidRequestError``, and 500
            otherwise, including a library error about malformed data.
        """
        match error:
            case AmbiguousAddressError():
                return HTTPStatus.CONFLICT
            case LookupError():
                return HTTPStatus.NOT_FOUND
            case DatasetNotImportedError() | UnsupportedDatabaseError():
                return HTTPStatus.SERVICE_UNAVAILABLE
            case InvalidRequestError():
                return HTTPStatus.BAD_REQUEST
            case _:
                return HTTPStatus.INTERNAL_SERVER_ERROR
