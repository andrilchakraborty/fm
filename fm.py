import json
import asyncio
import aiohttp
import httpx
from typing import Optional

from fastapi import FastAPI, HTTPException, Response, Request
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pyppeteer import launch

# ——— Your Last.fm credentials & settings ——————————————————————
LASTFM_API_KEY    = "9ae3431bba6f1f3e9ebdcec25898847c"
LASTFM_SHARED_SEC = "631fdc5966a5ee09c383b2e2dde5b2d7"
API_ROOT          = "https://ws.audioscrobbler.com/2.0/"
RECENT_METHOD     = "user.getrecenttracks"
USER_DATA_FILE    = "lastfm_users.json"
SERVICE_URL       = "https://fm-o04f.onrender.com"
# ——— Load user→Last.fm mapping ——————————————————————————
with open(USER_DATA_FILE, "r") as f:
    user_map = json.load(f)

# ——— Helpers for Last.fm ————————————————————————————————
async def try_url(session: aiohttp.ClientSession, url: str) -> bool:
    try:
        async with session.head(url, timeout=5) as resp:
            return resp.status == 200
    except:
        return False

async def fetch_lastfm_data(user_id: int) -> Optional[dict]:
    entry = user_map.get(str(user_id))
    if not entry or "username" not in entry:
        return None

    username    = entry["username"]
    session_key = entry.get("session")

    async with aiohttp.ClientSession() as session:
        # 1) recent track
        rp = {
            "method":  RECENT_METHOD,
            "user":    username,
            "api_key": LASTFM_API_KEY,
            "format":  "json",
            "limit":   1
        }
        if session_key:
            rp["sk"] = session_key

        async with session.get(API_ROOT, params=rp) as r:
            recent = await r.json()

        tracks = recent.get("recenttracks", {}).get("track", [])
        if not tracks:
            return None
        t = tracks[0]
        artist     = t["artist"]["#text"]
        title      = t["name"]
        track_url  = t["url"]
        nowplaying = t.get("@attr", {}).get("nowplaying") == "true"
        total_scrobbles = int(recent["recenttracks"]["@attr"]["total"])

        # 2) track.getInfo with user → playcount + album
        ip = {
            "method":      "track.getInfo",
            "api_key":     LASTFM_API_KEY,
            "artist":      artist,
            "track":       title,
            "user":        username,
            "autocorrect": "1",
            "format":      "json"
        }
        async with session.get(API_ROOT, params=ip) as r2:
            info = await r2.json()
        ti = info.get("track", {}) or {}
        user_playcount = int(ti.get("userplaycount", 0))
        album_data     = ti.get("album", {}) or {}
        album_name     = album_data.get("title", "")

        # 3) fallback generic getInfo if no album
        if not album_name:
            gen = ip.copy()
            gen.pop("user", None)
            async with session.get(API_ROOT, params=gen) as r3:
                geninfo = await r3.json()
            album_data = geninfo.get("track", {}).get("album", {}) or {}
            album_name = album_data.get("title", "")

        # 4) build image candidates
        candidates = []
        for img in reversed(t.get("image", [])):
            if img.get("#text"):
                candidates.append(img["#text"])
        for img in reversed(album_data.get("image", [])):
            if img.get("#text"):
                candidates.append(img["#text"])
        mbid = t.get("album", {}).get("mbid")
        if mbid:
            candidates.append(
                f"https://lastfm.freetls.fastly.net/i/u/300x300/{mbid}.jpg?format=webp"
            )

        # artist images
        ap = {
            "method":  "artist.getInfo",
            "artist":  artist,
            "api_key": LASTFM_API_KEY,
            "format":  "json"
        }
        async with session.get(API_ROOT, params=ap) as r4:
            ainfo = await r4.json()
        for img in reversed(ainfo.get("artist", {}).get("image", [])):
            if img.get("#text"):
                candidates.append(img["#text"])

        image_url = None
        for url in candidates:
            if await try_url(session, url):
                image_url = url
                break

    # assemble plain‐dict “embed”
    color = 0x57F287 if nowplaying else 0x5865F2
    return {
        "title":       title,
        "url":         track_url,
        "description": artist,
        "color":       color,
        "author":      f"{username} on Last.fm",
        "thumbnail":   image_url or "",
        "footer": {
            "text": (
                f"Playcount: {user_playcount} ∙ "
                f"Total Scrobbles: {total_scrobbles} ∙ "
                f"Album: {album_name or 'N/A'}"
            )
        }
    }

# ——— FastAPI app & setup ————————————————————————————————
app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/ping")
async def ping():
    return {"status": "alive"}

@app.on_event("startup")
async def schedule_ping():
    async def pinger():
        async with httpx.AsyncClient(timeout=5) as client:
            while True:
                try:
                    await client.get(f"{SERVICE_URL}/ping")
                except:
                    pass
                await asyncio.sleep(120)
    asyncio.create_task(pinger())

# ——— Browser startup/shutdown —————————————————————————————
browser = None

@app.on_event("startup")
async def startup_browser():
    global browser
    browser = await launch(headless=True, args=[
        "--no-sandbox", "--disable-setuid-sandbox"
    ])

@app.on_event("shutdown")
async def shutdown_browser():
    await browser.close()

# ——— Last.fm JSON “embed” endpoint ————————————————————————
class EmbedResponse(BaseModel):
    title: str
    url: str
    description: str
    color: int
    author: str
    thumbnail: Optional[str]
    footer: dict

@app.get("/lastfm/{user_id}", response_model=EmbedResponse)
async def lastfm_embed(user_id: int):
    data = await fetch_lastfm_data(user_id)
    if not data:
        raise HTTPException(404, "User not found or no recent tracks")
    return data

# ——— Your original HTML render endpoint ——————————————————————
@app.get(
    "/render",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}}
)
async def render(
    artist: str,
    title: str,
    guild: str,
    type: str = "WhoKnows Track",
    user: Optional[str] = None,
):
    try:
        # 1) fetch who‑knows data
        plays = []
        for disp, usr in await lookup_members(guild):
            info = await fetch_json(
                API_ROOT,
                {
                    "method":  "track.getInfo",
                    "artist":  artist,
                    "track":   title,
                    "user":    usr,
                    "api_key": LASTFM_API_KEY,
                    "format":  "json",
                },
            )
            cnt = int(info.get("track", {}).get("userplaycount", 0))
            if cnt > 0:
                plays.append((disp, cnt))

        if not plays:
            # no one’s played it
            raise HTTPException(404, "no plays")

        # sort & slice
        plays.sort(key=lambda x: x[1], reverse=True)
        top10 = plays[:10]
        total_listeners = len(plays)
        total_plays = sum(c for _, c in plays)
        avg = total_plays // total_listeners

        # 2) pick image url
        image_url = await pick_image_url(artist, title)

        # 3) render HTML via Jinja2 + Pyppeteer
        html = templates.get_template("wkt.html").render(
            type=type,
            title=f"{title} by {artist}",
            location=f"in {guild}",
            image_url=image_url or "",
            users="".join(
                f"<li><span class='num'>{i}.</span> {name} <span class='num'>{cnt}</span></li>"
                for i, (name, cnt) in enumerate(top10, start=1)
            ),
            listeners=total_listeners,
            plays=total_plays,
            average=avg,
            crown_hide="hidden",
            hide_img="" if image_url else "hidden",
            **{"num-width": 48},
        )

        page = await browser.newPage()
        await page.setViewport({"width": 1000, "height": 600})
        await page.setContent(html, waitUntil="networkidle0")
        png = await page.screenshot(type="png")
        await page.close()

        return Response(content=png, media_type="image/png")

    except HTTPException:
        # re-raise HTTPExceptions (404 etc) unmodified
        raise
    except Exception as e:
        # log full traceback for debugging
        traceback.print_exc()
        # return 500 with error type & message
        raise HTTPException(500, detail=f"Render error: {type(e).__name__}: {e}")
