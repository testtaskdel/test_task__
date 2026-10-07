from secrets import compare_digest

from fastapi import Depends, Header, HTTPException, status

from app.config import get_settings


def require_api_key(x_api_key: str = Header(alias="X-API-Key")) -> None:
    expected = get_settings().api_key
    if not compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


ApiKey = Depends(require_api_key)
