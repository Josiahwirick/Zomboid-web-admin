from __future__ import annotations

import httpx

STEAM_DETAILS_URL = "https://api.steampowered.com/ISteamRemoteStorage/GetPublishedFileDetails/v1/"


def fetch_workshop_titles(workshop_ids: list[str], timeout: float = 8.0) -> dict[str, str]:
    ids = [wid for wid in workshop_ids if wid.isdigit()]
    if not ids:
        return {}
    data: dict[str, str | int] = {"itemcount": len(ids)}
    for i, wid in enumerate(ids):
        data[f"publishedfileids[{i}]"] = wid
    try:
        response = httpx.post(STEAM_DETAILS_URL, data=data, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return {}
    titles: dict[str, str] = {}
    files = payload.get("response", {}).get("publishedfiledetails", [])
    for item in files:
        file_id = str(item.get("publishedfileid", ""))
        title = item.get("title") or ""
        if file_id and title:
            titles[file_id] = title
    return titles
