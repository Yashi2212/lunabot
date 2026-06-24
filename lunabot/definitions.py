from __future__ import annotations

import aiohttp

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/"


class DefinitionNotFound(Exception):
    pass


async def fetch_meaning(word: str) -> dict:
    """Fetch a clean definition from the free DictionaryAPI.dev service."""
    url = f"{API_URL}{word.lower()}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                raise DefinitionNotFound(f"No definition found for '{word}'")
            body = await response.json()

    if not isinstance(body, list) or not body:
        raise DefinitionNotFound(f"No definition found for '{word}'")

    entry = body[0]
    meanings = []
    for meaning in entry.get("meanings", []):
        definitions = meaning.get("definitions", [])
        if not definitions:
            continue
        meanings.append(
            {
                "partOfSpeech": meaning.get("partOfSpeech", ""),
                "definitions": [
                    {
                        "definition": definitions[0].get("definition", "No definition available."),
                        "example": definitions[0].get("example"),
                    }
                ],
            }
        )

    if not meanings:
        raise DefinitionNotFound(f"No definition found for '{word}'")

    return {
        "word": entry.get("word", word),
        "phonetic": entry.get("phonetic", ""),
        "meanings": meanings,
    }
