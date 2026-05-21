#!/usr/bin/env python3
"""Two Lines 슬라이드(0cdbd9c6)에 도달하는 theme API 경로 탐색."""
import asyncio
from urllib.parse import quote

import httpx

BASE = "http://100.99.47.84:12135"
TARGET_UUID = "0cdbd9c6-7ffd-45dc-8bef-fce91f8d9202"


async def main() -> None:
    async with httpx.AsyncClient(timeout=12) as client:
        catalog = (await client.get(f"{BASE}/v1/themes")).json()
        theme_ids: list[str] = []
        for group in catalog.get("groups") or []:
            for theme in group.get("themes") or []:
                tid = theme.get("id", {})
                name = tid.get("name")
                if name:
                    theme_ids.append(str(name))
                theme_ids.append(str(tid.get("index", 0)))
        for theme in catalog.get("themes") or []:
            tid = theme.get("id", {})
            if tid.get("name"):
                theme_ids.append(str(tid["name"]))
            theme_ids.append(str(tid.get("index", 0)))

        seen_t: set[str] = set()
        for th in theme_ids:
            if th in seen_t:
                continue
            seen_t.add(th)
            for si in range(0, 12):
                path = f"/v1/theme/{quote(th, safe='')}/slides/{si}"
                resp = await client.get(f"{BASE}{path}")
                if resp.status_code >= 400:
                    continue
                body = resp.json()
                uid = (body.get("id") or {}).get("uuid", "")
                uname = (body.get("id") or {}).get("name", "")
                if uid == TARGET_UUID:
                    print("FOUND", th, si, uname, path)
                    return
        print("not found — Lyric Styles/Black Box 는 PP API 전역 인덱스로 노출되지 않을 수 있음")


if __name__ == "__main__":
    asyncio.run(main())
