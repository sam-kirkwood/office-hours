"""Internal-service auth: a single shared bearer token between Next.js and this
service. Trusted user base, no mTLS or per-caller identity required."""

from fastapi import Depends, Header, HTTPException, status

from config import Settings, get_settings


def require_internal_token(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    expected = f"Bearer {settings.internal_api_token}"
    if authorization != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")
