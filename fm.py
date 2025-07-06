# app.py

import json
import asyncio
import aiohttp
import httpx
import traceback

from typing import Optional, List, Tuple
from fastapi import FastAPI, HTTPException, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pyppeteer import launch

# ——— CONFIG ———————————————————————————————————————————————
LASTFM_API_KEY    = "9ae3431bba6f1f3e9ebdcec25898847c"
API_ROOT          = "https://ws.audioscrobbler.com/2.0/"
USER_DATA_FILE    = "lastfm_users.json"   # maps Discord user ID → {"username": "...", "session": "..."} 
SERVICE_URL       = "https://fm-o04f.onrender.com"

# ——— LOAD YOUR LAST.FM USER MAPPING —————————————————————————
with open(USER_DATA_FILE, "r") as f:
    user_map = json.load(f)
    # e.g. { "123456789012345678": { "username": "alice_lfm", "session": "..." }, … }

# ——— FASTAPI + TEMPLATES + BROWSER ————————————————————————
app       = FastAPI()
templates = Jinja2Templates(directory="templates")
browser   = None

@app.on_event("startup")
async def startup_event():
    global browser
    browser = await launch(headless=True,
                           args=["--no-sandbox", "--disable-setuid-sandbox"])
    # optional: schedule a periodic ping so Heroku/Render stays awake
    async def pinger():
        async with httpx.AsyncClient(timeout=5) as client:
            while True:
                try:
                    await client.get(f"{SERVICE_URL}/ping")
                except:
                    pass
                await asyncio.sleep(120)
    asyncio.create_task(pinger())

@app.on_event("shutdown")
async def shutdown_event():
    await browser.close()

@app.get("/ping")
async def ping():
    return {"status": "alive"}

# ——— HELPERS ——————————————————————————————————————————————

async def try_url(session: aiohttp.ClientSession, url: str) -> bool:
    """Return True if HEAD to url yields 200."""
    try:
        async with session.head(url, timeout=5) as resp:
            return resp.status == 200
    except:
        return False

async def fetch_json(base_url: str, params: dict) -> dict:
    """GET JSON from Last.fm (or any) endpoint."""
    async with aiohttp.ClientSession() as sess:
        async with sess.get(base_url, params=params) as resp:
            return await resp.json()

async def lookup_members(guild_name: str) -> List[Tuple[str,str]]:
    """
    Return a list of (display_name, lastfm_username) for this guild.
    Here we cheat and use user_map: you’ll want to integrate your Discord bot cache/API.
    """
    return [
        (f"User {uid}", entry["username"])
        for uid,entry in user_map.items()
    ]

async def pick_image_url(artist: str, title: str) -> Optional[str]:
    """
    Find the best cover/artist image from Last.fm.
    Tries: track images → album images → artist images.
    """
    candidates = []
    # 1) track.getInfo (no user)
    track_info = await fetch_json(
        API_ROOT,
        {"method":"track.getInfo",
         "api_key": LASTFM_API_KEY,
         "artist": artist,
         "track": title,
         "autocorrect":"1",
         "format":"json"}
    )
    for img in track_info.get("track",{}).get("album",{}).get("image",[]):
        if img.get("#text"): candidates.append(img["#text"])
    for img in track_info.get("track",{}).get("toptags",{}).get("tag",[]):
        # sometimes tags have images? (optional)
        pass

    # 2) artist.getInfo
    artist_info = await fetch_json(
        API_ROOT,
        {"method":"artist.getInfo",
         "api_key": LASTFM_API_KEY,
         "artist": artist,
         "format":"json"}
    )
    for img in artist_info.get("artist",{}).get("image",[]):
        if img.get("#text"): candidates.append(img["#text"])

    # 3) HEAD-check each
    async with aiohttp.ClientSession() as session:
        for url in candidates:
            if await try_url(session, url):
                return url
    return None

async def fetch_lastfm_data(user_id: int) -> Optional[dict]:
    """
    Your existing “embed” logic, unchanged.
    Returns the JSON embed dict for a single user.
    """
    entry = user_map.get(str(user_id))
    if not entry or "username" not in entry:
        return None

    username = entry["username"]
    session_key = entry.get("session")

    # 1) recent track
    params = {
        "method": "user.getrecenttracks",
        "user": username,
        "api_key": LASTFM_API_KEY,
        "format": "json",
        "limit": 1
    }
    if session_key: params["sk"] = session_key

    recent = await fetch_json(API_ROOT, params)
    tracks = recent.get("recenttracks", {}).get("track", [])
    if not tracks: return None
    t = tracks[0]
    artist = t["artist"]["#text"]
    title  = t["name"]
    track_url = t["url"]
    nowplaying = t.get("@attr",{}).get("nowplaying") == "true"
    total_scrobbles = int(recent["recenttracks"]["@attr"]["total"])

    # 2) track.getInfo w/ user
    ip = {
        "method":"track.getInfo",
        "artist":artist,
        "track":title,
        "user":username,
        "api_key":LASTFM_API_KEY,
        "autocorrect":"1",
        "format":"json"
    }
    user_info = await fetch_json(API_ROOT, ip)
    ti = user_info.get("track", {}) or {}
    user_playcount = int(ti.get("userplaycount",0))
    album_name = ti.get("album",{}).get("title","")

    # 3) fallback if no album
    if not album_name:
        gen = ip.copy(); gen.pop("user",None)
        geninfo = await fetch_json(API_ROOT, gen)
        album_name = geninfo.get("track",{}).get("album",{}).get("title","")

    # 4) pick thumbnail
    candidates = []
    for img in reversed(t.get("image",[])):
        if img.get("#text"): candidates.append(img["#text"])
    for img in reversed(t.get("album",{}).get("image",[])):
        if img.get("#text"): candidates.append(img["#text"])
    mbid = t.get("album",{}).get("mbid")
    if mbid:
        candidates.append(
            f"https://lastfm.freetls.fastly.net/i/u/300x300/{mbid}.jpg?format=webp"
        )
    artist_info = await fetch_json(
        API_ROOT,
        {"method":"artist.getInfo","artist":artist,"api_key":LASTFM_API_KEY,"format":"json"}
    )
    for img in reversed(artist_info.get("artist",{}).get("image",[])):
        if img.get("#text"): candidates.append(img["#text"])

    thumbnail = ""
    async with aiohttp.ClientSession() as session:
        for url in candidates:
            if await try_url(session, url):
                thumbnail = url
                break

    color = 0x57F287 if nowplaying else 0x5865F2
    return {
        "title":       title,
        "url":         track_url,
        "description": artist,
        "color":       color,
        "author":      f"{username} on Last.fm",
        "thumbnail":   thumbnail,
        "footer": {
            "text":(
                f"Playcount: {user_playcount} ∙ "
                f"Total Scrobbles: {total_scrobbles} ∙ "
                f"Album: {album_name or 'N/A'}"
            )
        }
    }

# ——— YOUR “WHO KNOWS” RENDER ENDPOINT ——————————————————————
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
        # 1) find who knows this track
        plays: List[Tuple[str,int]] = []
        for display_name, lfm_user in await lookup_members(guild):
            info = await fetch_json(
                API_ROOT,
                {
                    "method":"track.getInfo",
                    "artist": artist,
                    "track":  title,
                    "user":   lfm_user,
                    "api_key":LASTFM_API_KEY,
                    "format":"json"
                }
            )
            cnt = int(info.get("track",{}).get("userplaycount",0))
            if cnt > 0:
                plays.append((display_name, cnt))

        if not plays:
            raise HTTPException(404, "no plays")

        plays.sort(key=lambda x: x[1], reverse=True)
        top10 = plays[:10]
        total_listeners = len(plays)
        total_plays     = sum(cnt for _,cnt in plays)
        average         = total_plays // total_listeners

        # 2) pick a background image
        image_url = await pick_image_url(artist, title)

        # 3) render HTML → PNG
        html = templates.get_template("wkt.html").render(
            type=type,
            title=f"{title} by {artist}",
            location=f"in {guild}",
            image_url=image_url or "",
            users="".join(
                f"<li><span class='num'>{i}.</span> {name} "
                f"<span class='num'>{cnt}</span></li>"
                for i,(name,cnt) in enumerate(top10, start=1)
            ),
            listeners=total_listeners,
            plays=total_plays,
            average=average,
            num_width=48,
            hide_img="" if image_url else "hidden",
            crown_hide="hidden",
            crown_text="",  # optional
        )

        page = await browser.newPage()
        await page.setViewport({"width":1000,"height":600})
        await page.setContent(html, waitUntil="networkidle0")
        png = await page.screenshot(type="png")
        await page.close()

        return Response(content=png, media_type="image/png")

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(500, detail=f"Render error: {type(e).__name__}: {e}")
