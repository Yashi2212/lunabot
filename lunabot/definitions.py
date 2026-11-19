"""Dictionary providers used by word games."""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

import aiohttp


DICTIONARY_API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"
FREE_DICTIONARY_API_URL = "https://freedictionaryapi.com/api/v1/entries/en/"
DEFAULT_LOOKUP_TIMEOUT_SECONDS = 1.2
PROVIDER_TIMEOUT_SECONDS = 0.6


class DefinitionNotFound(Exception):
    """The providers responded, but none contains the requested word."""


class DictionaryUnavailable(Exception):
    """No dictionary provider could be reached for this lookup."""


async def fetch_meaning(
    word: str,
    session: aiohttp.ClientSession | None = None,
    timeout_seconds: float = DEFAULT_LOOKUP_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return a normalized definition, trying both free providers.

    A missing word is different from an outage: ``DefinitionNotFound`` means at
    least one provider answered normally, while ``DictionaryUnavailable`` means
    every provider failed or timed out. This lets games avoid rejecting a
    player's answer when verification was impossible.
    """
    owns_session = session is None
    if owns_session:
        session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout_seconds)
        )

    providers: tuple[Callable[[str, aiohttp.ClientSession], Awaitable[dict[str, Any]]], ...] = (
        _fetch_dictionary_api,
        _fetch_free_dictionary_api,
    )
    provider_responded = False
    deadline = asyncio.get_running_loop().time() + max(0.1, timeout_seconds)

    try:
        for provider in providers:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                break
            try:
                result = await asyncio.wait_for(
                    provider(word, session),
                    timeout=min(PROVIDER_TIMEOUT_SECONDS, remaining),
                )
            except DefinitionNotFound:
                provider_responded = True
                continue
            except (aiohttp.ClientError, TimeoutError, ValueError, asyncio.TimeoutError):
                continue
            provider_responded = True
            return result
    finally:
        if owns_session and session is not None:
            await session.close()

    if provider_responded:
        raise DefinitionNotFound(f"No definition found for '{word}'")
    raise DictionaryUnavailable("All dictionary providers are unavailable")


async def _fetch_dictionary_api(
    word: str,
    session: aiohttp.ClientSession,
) -> dict[str, Any]:
    body = await _get_json(session, f"{DICTIONARY_API_URL}{word.lower()}")
    if not isinstance(body, list) or not body:
        raise DefinitionNotFound(f"No definition found for '{word}'")

    entry = body[0]
    if not isinstance(entry, dict):
        raise DefinitionNotFound(f"No definition found for '{word}'")

    meanings: list[dict[str, Any]] = []
    for meaning in entry.get("meanings", []):
        if not isinstance(meaning, dict):
            continue
        definitions = _clean_definitions(meaning.get("definitions", []))
        if definitions:
            meanings.append(
                {
                    "partOfSpeech": meaning.get("partOfSpeech", ""),
                    "definitions": definitions,
                }
            )
    if not meanings:
        raise DefinitionNotFound(f"No definition found for '{word}'")

    return {
        "word": entry.get("word", word),
        "phonetic": entry.get("phonetic", ""),
        "meanings": meanings,
        "sourceUrls": entry.get("sourceUrls", []),
        "provider": "DictionaryAPI.dev",
    }


async def _fetch_free_dictionary_api(
    word: str,
    session: aiohttp.ClientSession,
) -> dict[str, Any]:
    body = await _get_json(session, f"{FREE_DICTIONARY_API_URL}{word.lower()}")
    if not isinstance(body, dict):
        raise DefinitionNotFound(f"No definition found for '{word}'")

    meanings: list[dict[str, Any]] = []
    for entry in body.get("entries", []):
        if not isinstance(entry, dict):
            continue
        definitions = []
        for sense in (entry.get("senses") or [])[:2]:
            if not isinstance(sense, dict):
                continue
            definition = str(sense.get("definition", "")).strip()
            if not definition:
                continue
            examples = sense.get("examples") or []
            definitions.append(
                {
                    "definition": definition,
                    "example": examples[0] if examples else None,
                    "synonyms": (sense.get("synonyms") or [])[:5],
                }
            )
        if definitions:
            meanings.append(
                {
                    "partOfSpeech": entry.get("partOfSpeech", ""),
                    "definitions": definitions,
                }
            )
    if not meanings:
        raise DefinitionNotFound(f"No definition found for '{word}'")

    source = body.get("source") or {}
    source_url = source.get("url") if isinstance(source, dict) else None
    return {
        "word": body.get("word", word),
        "meanings": meanings,
        "sourceUrls": [source_url] if source_url else [],
        "provider": "FreeDictionaryAPI.com",
    }


async def _get_json(session: aiohttp.ClientSession, url: str) -> Any:
    async with session.get(url) as response:
        if response.status == 404:
            raise DefinitionNotFound("Word not found")
        if response.status == 429 or response.status >= 500:
            raise aiohttp.ClientResponseError(
                response.request_info,
                response.history,
                status=response.status,
                message="Dictionary provider unavailable",
                headers=response.headers,
            )
        if response.status != 200:
            raise DefinitionNotFound("Word not found")
        return await response.json(content_type=None)


def _clean_definitions(values: Any) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for item in values[:2]:
        if not isinstance(item, dict):
            continue
        definition = str(item.get("definition", "")).strip()
        if definition:
            cleaned.append(
                {
                    "definition": definition,
                    "example": item.get("example"),
                    "synonyms": (item.get("synonyms") or [])[:5],
                }
            )
    return cleaned
