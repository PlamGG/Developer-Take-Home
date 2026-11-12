from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import SplitBillException
from app.routers import router


def create_app() -> FastAPI:
    app = FastAPI(title="SplitBill API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", "X-User", "Idempotency-Key"],
    )

    @app.exception_handler(SplitBillException)
    async def splitbill_exception_handler(_: Request, exc: SplitBillException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "validation_error", "message": str(exc)}},
        )

    app.include_router(router)
    return app


app = create_app()
