import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from http import HTTPStatus
from importlib.metadata import version
from typing import ClassVar

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from address_codec_jp.api.address_routes import AddressRoutes
from address_codec_jp.api.codec_pool import CodecPool
from address_codec_jp.api.error_status import ErrorStatus
from address_codec_jp.api.invalid_request_error import InvalidRequestError
from address_codec_jp.api.service_settings import ServiceSettings
from address_codec_jp.errors.address_codec_error import AddressCodecError
from address_codec_jp.serialization.error_serializer import ErrorSerializer
from address_codec_jp.serialization.json_value import JsonValue

_LOGGER: logging.Logger = logging.getLogger(__name__)


class ApplicationFactory:
    """
    Builder of the FastAPI application of the web API.

    The cache must have been prepared, e.g. by ``address-codec-jp cache prepare`` at
    image build time; the application fails at creation when it has not been built.
    Run it with ``uvicorn --factory
    address_codec_jp.api:ApplicationFactory.from_environment``, with as many worker
    processes as the cores to use.

    Errors of the request are answered with their message; any other failure is logged
    and answered with a generic 500 body, so that no internal detail leaks.

    Parameters
    ----------
    settings : ServiceSettings
        Configuration of the service.
    """

    TERMS_OF_USE: ClassVar[str] = (
        "## 利用条件\n\n"
        + "- データを利用・公開する際は、応答の `attribution` に示す出典を記載してください。"
        + "編集・加工した場合は、その旨と加工した者も記載し、国が作成したかのような態様で"
        + "公表しないでください。\n"
        + "- 登記所備付地図データ（地番の点と地番のポリゴンを含む）を他の情報と照合する等して"
        + "特定の個人を識別してはいけません（登記所備付地図データ利用規約 3）カ）。\n"
        + "- 登記所備付地図データは明治時代から現代までの図面に基づき、精度が一様ではありません。"
        + "登記所が交付する証明書の代わりにはなりません。\n"
        + "- デジタル庁、総務省統計局、法務省は、データを用いて行う一切の行為について"
        + "責任を負いません。"
    )

    INTERNAL_ERROR_BODY: ClassVar[dict[str, JsonValue]] = {
        "error": "Internal server error.",
        "error_type": "InternalServerError",
    }

    def __init__(self, settings: ServiceSettings) -> None:
        self._settings: ServiceSettings = settings
        self._error_status: ErrorStatus = ErrorStatus()
        self._error_serializer: ErrorSerializer = ErrorSerializer()

    @classmethod
    def from_environment(cls) -> FastAPI:
        """
        Create the application configured by environment variables.

        Returns
        -------
        FastAPI
            Application with ``ServiceSettings.from_environment(os.environ)``.

        Raises
        ------
        ValueError
            If a variable is malformed.
        DatasetNotImportedError
            If the cache has not been built.
        """
        return cls(ServiceSettings.from_environment(os.environ)).create()

    def create(self) -> FastAPI:
        """
        Create the application.

        Returns
        -------
        FastAPI
            Application whose worker threads close their codecs on shutdown.

        Raises
        ------
        DatasetNotImportedError
            If the cache has not been built.
        UnsupportedDatabaseError
            If the cache holds a database of another version.
        """
        pool = CodecPool(self._settings.cache_directory, self._settings.thread_count)
        pool.check()

        @asynccontextmanager
        async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
            yield
            pool.close()

        application = FastAPI(
            title="AddressCodecJP",
            version=version("address-codec-jp"),
            summary="Japanese addresses, address codes, points, and shapes.",
            description=self.TERMS_OF_USE,
            lifespan=lifespan,
        )
        application.include_router(AddressRoutes(pool, self._settings).build_router())
        application.add_exception_handler(AddressCodecError, self._respond_error)
        application.add_exception_handler(InvalidRequestError, self._respond_error)
        application.add_exception_handler(Exception, self._respond_internal_error)
        return application

    def _respond_error(self, request: Request, error: Exception) -> JSONResponse:
        status = self._error_status.of(error)
        if status is HTTPStatus.INTERNAL_SERVER_ERROR:
            _LOGGER.error("Request to %s failed.", request.url.path, exc_info=error)
            return self._respond_internal_error(request, error)
        return JSONResponse(self._error_serializer.serialize(error), status_code=int(status))

    def _respond_internal_error(self, _: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            self.INTERNAL_ERROR_BODY, status_code=int(HTTPStatus.INTERNAL_SERVER_ERROR)
        )
