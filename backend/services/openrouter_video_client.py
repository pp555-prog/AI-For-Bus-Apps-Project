"""OpenRouter video generation client."""

from __future__ import annotations

import httpx

from backend.config import settings


class OpenRouterVideoError(RuntimeError):
    """Raised when OpenRouter video generation fails."""


def is_configured() -> bool:
    return bool(settings.OPENROUTER_API_KEY)


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }


async def submit_video(prompt: str, input_references: list[str] | None = None) -> dict:
    """Submit an async OpenRouter video generation job."""
    if not settings.OPENROUTER_API_KEY:
        raise OpenRouterVideoError("OPENROUTER_API_KEY is not configured")

    payload: dict = {
        "model": settings.OPENROUTER_VIDEO_MODEL,
        "prompt": prompt,
        "duration": settings.OPENROUTER_VIDEO_DURATION,
        "resolution": settings.OPENROUTER_VIDEO_RESOLUTION,
        "aspect_ratio": settings.OPENROUTER_VIDEO_ASPECT_RATIO,
        "generate_audio": False,
    }
    if input_references:
        payload["input_references"] = [
            {"type": "image_url", "image_url": {"url": url}}
            for url in input_references[:4]
        ]

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
            response = await client.post(
                f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/videos",
                json=payload,
                headers=_headers(),
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenRouterVideoError(
            f"OpenRouter video submit returned {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise OpenRouterVideoError(f"OpenRouter video submit failed: {exc}") from exc

    return response.json()


async def get_video_job(job_id: str) -> dict:
    """Fetch an OpenRouter video generation job status."""
    if not settings.OPENROUTER_API_KEY:
        raise OpenRouterVideoError("OPENROUTER_API_KEY is not configured")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.get(
                f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/videos/{job_id}",
                headers=_headers(),
            )
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise OpenRouterVideoError(
            f"OpenRouter video poll returned {exc.response.status_code}: "
            f"{exc.response.text}"
        ) from exc
    except httpx.HTTPError as exc:
        raise OpenRouterVideoError(f"OpenRouter video poll failed: {exc}") from exc

    return response.json()
