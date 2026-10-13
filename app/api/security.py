import hmac

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


def require_admin_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected_key = get_settings().admin_api_key
    supplied_key = x_api_key or ""
    if not expected_key or not hmac.compare_digest(supplied_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "message": "Valid API key required.",
            },
        )
