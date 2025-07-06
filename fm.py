import json
import asyncio
import aiohttp
import httpx
import traceback
from typing import Optional, List, Tuple
from fastapi import FastAPI, HTTPException, Response
from fastapi.templating import Jinja2Templates
from pyppeteer import launch
import builtins

# ——— CONFIG ———————————————————————————————————————————————
LASTFM_API_KEY = "9ae3431bba6f1f3e9ebdcec25898847c"
API_ROOT       = "https://ws.audioscrobbler.com/2.0/"
USER_DATA_FILE = "lastfm_users.json"
SERVICE_URL    = "https://fm-o04f.onrender.com"

# ——— LOAD USER MAP ——————————————————————————————————————
with open(USER_DATA_FILE, "r") as f:
    user_map = json.load(f)

# ——— FASTAPI + TEMPLATES + BROWSER ————————————————————————
app       = FastAPI()
templates = Jinja2Templates(directory="templates")
browser   = None

@app.on_event("startup")
async def on_startup():
    global browser
    browser = await launch(
        headless=True,
        args=["--no-sandbox", "--disable-setuid-sandbox"]
    )
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
async def on_shutdown():
    await browser.close()

@app.get("/ping")
async def ping():
    return {"status": "alive"}

# ——— HELPERS ——————————————————————————————————————————————
async def try_url(session: aiohttp.ClientSession, url: str) -> bool:
    try:
        async with session.head(url, timeout=5) as resp:
            return resp.status == 200
    except:
        return False

async def fetch_json(base_url: str, params: dict) -> dict:
    async with aiohttp.ClientSession() as sess:
        async with sess.get(base_url, params=params) as resp:
            return await resp.json()

async def lookup_members(guild_name: str) -> List[Tuple[str,str]]:
    return [
        (f"User {uid}", entry["username"])
        for uid, entry in user_map.items()
        if "username" in entry
    ]

async def pick_image_url(artist: str, title: str) -> Optional[str]:
    candidates = []
    info = await fetch_json(API_ROOT, {
        "method":"track.getInfo",
        "api_key": LASTFM_API_KEY,
        "artist": artist,
        "track": title,
        "autocorrect":"1",
        "format":"json"
    })
    for img in info.get("track", {}).get("album", {}).get("image", []):
        if img.get("#text"): candidates.append(img["#text"])
    ainfo = await fetch_json(API_ROOT, {
        "method":"artist.getInfo",
        "artist": artist,
        "api_key": LASTFM_API_KEY,
        "format":"json"
    })
    for img in ainfo.get("artist", {}).get("image", []):
        if img.get("#text"): candidates.append(img["#text"])
    async with aiohttp.ClientSession() as session:
        for url in candidates:
            if await try_url(session, url):
                return url
    return None

async def fetch_lastfm_data(user_id: int) -> Optional[dict]:
    entry = user_map.get(str(user_id))
    if not entry or "username" not in entry:
        return None
    username    = entry["username"]
    session_key = entry.get("session")
    params = {
        "method":"user.getrecenttracks",
        "user":username,
        "api_key":LASTFM_API_KEY,
        "format":"json",
        "limit":1
    }
    if session_key: params["sk"] = session_key
    recent = await fetch_json(API_ROOT, params)
    tracks = recent.get("recenttracks", {}).get("track", [])
    if not tracks: return None
    t = tracks[0]
    artist     = t["artist"]["#text"]
    title      = t["name"]
    track_url  = t["url"]
    nowplaying = t.get("@attr",{}).get("nowplaying") == "true"
    total_scrobbles = int(recent["recenttracks"]["@attr"]["total"])
    ip = {
        "method":"track.getInfo",
        "artist":artist,
        "track":title,
        "user":username,
        "api_key":LASTFM_API_KEY,
        "autocorrect":"1",
        "format":"json"
    }
    info = await fetch_json(API_ROOT, ip)
    ti = info.get("track", {}) or {}
    user_playcount = int(ti.get("userplaycount", 0))
    album_name     = ti.get("album", {}).get("title", "")
    if not album_name:
        gen = ip.copy(); gen.pop("user", None)
        geninfo = await fetch_json(API_ROOT, gen)
        album_name = geninfo.get("track",{}).get("album",{}).get("title","")
    candidates = []
    for img in reversed(t.get("image", [])):
        if img.get("#text"): candidates.append(img["#text"])
    mbid = t.get("album", {}).get("mbid")
    if mbid:
        candidates.append(f"https://lastfm.freetls.fastly.net/i/u/300x300/{mbid}.jpg?format=webp")
    ainfo = await fetch_json(API_ROOT, {
        "method":"artist.getInfo",
        "artist":artist,
        "api_key":LASTFM_API_KEY,
        "format":"json"
    })
    for img in reversed(ainfo.get("artist", {}).get("image", [])):
        if img.get("#text"): candidates.append(img["#text"])
    thumbnail = ""
    async with aiohttp.ClientSession() as session:
        for url in candidates:
            if await try_url(session, url):
                thumbnail = url
                break
    color = 0x57F287 if nowplaying else 0x5865F2
    return {
        "title": title,
        "url": track_url,
        "description": artist,
        "color": color,
        "author": f"{username} on Last.fm",
        "thumbnail": thumbnail,
        "footer": {"text":f"Playcount: {user_playcount} ∙ Total Scrobbles: {total_scrobbles} ∙ Album: {album_name or 'N/A'}"}
    }

# ——— /render ENDPOINT ——————————————————————————————————————

@app.get(
    "/render",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}}
)
async def render(
    artist: str,
    title: str,
    guild: str,
    render_type: str = "WhoKnows Track",
    user: Optional[str] = None,
):
    try:
        plays: List[Tuple[str,int]] = []
        for display_name, lfm_user in await lookup_members(guild):
            info = await fetch_json(API_ROOT, {
                "method":"track.getInfo",
                "artist":artist,
                "track":title,
                "user":lfm_user,
                "api_key":LASTFM_API_KEY,
                "format":"json"
            })
            cnt = int(info.get("track",{}).get("userplaycount",0))
            if cnt>0:
                plays.append((display_name, cnt))
        if not plays:
            raise HTTPException(404, "no plays")
        plays.sort(key=lambda x: x[1], reverse=True)
        top10           = plays[:10]
        total_listeners = len(plays)
        total_plays     = sum(cnt for _,cnt in plays)
        average         = total_plays // total_listeners
        image_url       = await pick_image_url(artist, title)

        html = templates.get_template("wkt.html").render(
            type=render_type,
            title=f"{title} by {artist}",
            location=f"in {guild}",
            image_url=image_url or "",
            users="".join(
                f"<li><span class='num'>{i}.</span> {name} <span class='num'>{cnt}</span></li>"
                for i,(name,cnt) in enumerate(top10, start=1)
            ),
            listeners=total_listeners,
            plays=total_plays,
            average=average,
            num_width=48,
            hide_img="" if image_url else "hidden",
            crown_hide="hidden",
            crown_text="",
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
        detail = f"Render error: {builtins.type(e).__name__}: {e}"
        raise HTTPException(500, detail=detail)
