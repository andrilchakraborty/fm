# app.py — FastAPI render service

app = FastAPI()
jinja = Jinja2Templates(directory="templates")
browser = None

@app.on_event("startup")
async def startup():
    global browser
    browser = await launch(headless=True, args=["--no-sandbox","--disable-setuid-sandbox"])

@app.on_event("shutdown")
async def shutdown():
    await browser.close()

@app.get("/render", response_class=Response, responses={200: {"content": {"image/png": {}}}})
async def render(
    artist: str, title: str, guild: str,
    type: str = "WhoKnows Track",
    user: Optional[str] = None,
):
    # 1) fetch who‑knows data
    plays = []
    for disp, usr in await lookup_members(guild):
        info = await fetch_json(API_ROOT, { "method":"track.getInfo", "artist":artist, "track":title, "user":usr, "api_key":LASTFM_API_KEY, "format":"json" })
        cnt = int(info.get("track",{}).get("userplaycount",0))
        if cnt>0: plays.append((disp,cnt))
    if not plays:
        raise HTTPException(404, "no plays")
    plays.sort(key=lambda x:x[1], reverse=True)
    top10 = plays[:10]
    total_listeners = len(plays)
    total_plays     = sum(c for _,c in plays)
    avg             = total_plays//total_listeners

    # 2) pick image url
    image_url = await pick_image_url(artist,title)

    # 3) render HTML via jinja + pyppeteer
    html = jinja.get_template("wkt.html").render(
        type=type,
        title=f"{title} by {artist}",
        location=f"in {guild}",
        image_url=image_url or "",
        users="".join(f"<li><span class='num'>{i}.</span> {name} <span class='num'>{cnt}</span></li>"
                      for i,(name,cnt) in enumerate(top10, start=1)),
        listeners=total_listeners,
        plays=total_plays,
        average=avg,
        crown_hide="hidden",
        hide_img="" if image_url else "hidden",
        **{"num-width": 48}
    )

    page = await browser.newPage()
    await page.setViewport({"width":1000,"height":600})
    await page.setContent(html, waitUntil="networkidle0")
    png = await page.screenshot(type="png")
    await page.close()

    return Response(content=png, media_type="image/png")
