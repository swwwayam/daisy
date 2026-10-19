"""Check live Convex access approval without trusting a browser flag or email."""
import httpx
from fastapi import HTTPException


async def require_invited_user(site_url: str, token: str):
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                site_url.rstrip("/") + "/api/daisy/access",
                headers={"Authorization": "Bearer " + token},
            )
        if response.status_code == 401:
            raise HTTPException(status_code=401, detail="Sign in again to check your access.")
        response.raise_for_status()
        result = response.json()
        if not isinstance(result, dict) or type(result.get("approved")) is not bool:
            raise ValueError("Invalid access approval response")
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="Access approval service is temporarily unavailable.") from exc
    if result["approved"] is not True:
        raise HTTPException(status_code=403, detail="Request DAISY access and wait for approval before using the workspace.")
