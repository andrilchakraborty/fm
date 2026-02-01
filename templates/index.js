<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Bouncing Balls.exe – Close & Multiply</title>
  <style>
    body {
      margin: 0;
      height: 100vh;
      background: #000;
      color: #f44;
      font-family: Arial, sans-serif;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 2rem;
      font-size: 2.2rem;
      text-align: center;
    }
    button {
      font-size: 2.5rem;
      padding: 1.2rem 3.5rem;
      cursor: pointer;
      background: #f44;
      color: white;
      border: none;
      border-radius: 12px;
    }
    #status { font-size: 1.4rem; color: #aaa; max-width: 80%; }
  </style>
</head>
<body>

  <div id="start-screen">
    <div>r/balls bouncer – try closing them 😈</div>
    <button id="launch">LAUNCH CHAOS</button>
    <div id="status">Fetching real images from Reddit…</div>
  </div>

  <script>
    // ────────────────────────────────────────────────
    // CONFIG
    // ────────────────────────────────────────────────
    const SUBREDDIT    = "balls";
    const IMAGE_LIMIT  = 100;
    const POPUP_WIDTH  = 460;
    const POPUP_HEIGHT = 580;
    const VELOCITY     = 7;
    const TICK_MS      = 28;
    const MARGIN       = 50;
    const TOP_MARGIN   = 80;

    let imagePool = [];
    const activePopups = new Set();

    // ────────────────────────────────────────────────
    // Helpers
    // ────────────────────────────────────────────────
    function openPopupBlank(title = "Bouncing Balls.exe") {
      const left = (screen.availWidth  - POPUP_WIDTH)  / 2 + ((Math.random()*260 - 130)|0);
      const top  = (screen.availHeight - POPUP_HEIGHT) / 2 + ((Math.random()*180 - 90 )|0);

      const features = `width=${POPUP_WIDTH},height=${POPUP_HEIGHT},left=${left},top=${top},resizable=yes,scrollbars=no,status=no,toolbar=no,menubar=no,location=no`;

      const win = window.open("about:blank", "_blank", features);
      if (!win) alert("Popup blocked! Allow popups and try again.");
      return win;
    }

    function spawnBouncingWindow() {
      if (imagePool.length === 0) {
        alert("No images could be loaded from r/balls.\nCheck console for errors (CORS / rate limit / NSFW block).");
        return;
      }

      const imgUrl = imagePool[Math.random() * imagePool.length | 0];

      const html = `
<!DOCTYPE html>
<html>
<head>
  <title>Bouncing Balls – close if you dare</title>
  <style>
    body,html { margin:0; padding:0; height:100%; overflow:hidden; background:#000; }
    img { width:100%; height:100%; object-fit:contain; pointer-events:none; user-select:none; }
  </style>
</head>
<body>
  <img src="${imgUrl}" alt="r/${SUBREDDIT} image">
  <script>
    // Try to notify opener when closing (backup multiply trigger)
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage({type:'child_closing'}, '*');
    }
    // beforeunload attempt (usually blocked, but harmless)
    addEventListener('beforeunload', () => {
      try { for(let i=0;i<2;i++) opener?.spawnExtra?.(); } catch(e){}
    });
  </script>
</body>
</html>`;

      const win = openPopupBlank();
      if (!win) return;

      win.document.write(html);
      win.document.close();

      activePopups.add(win);

      setTimeout(() => startBouncing(win), 350);
    }

    function startBouncing(win) {
      if (!win || win.closed) return;

      let vx = VELOCITY * (Math.random() > 0.5 ? 1 : -1);
      let vy = VELOCITY * (Math.random() > 0.5 ? 1 : -1);

      function tick() {
        if (win.closed) return;

        let x = win.screenX;
        let y = win.screenY;
        let w = win.outerWidth  || POPUP_WIDTH;
        let h = win.outerHeight || POPUP_HEIGHT;

        if (x <= MARGIN)                 vx = +Math.abs(vx);
        if (x + w >= screen.availWidth  - MARGIN) vx = -Math.abs(vx);
        if (y <= TOP_MARGIN)             vy = +Math.abs(vy);
        if (y + h >= screen.availHeight - MARGIN) vy = -Math.abs(vy);

        win.moveBy(vx, vy);

        requestAnimationFrame(tick);   // smoother than setTimeout in many cases
      }

      tick();
    }

    // ────────────────────────────────────────────────
    // Fetch REAL images from r/balls (no placeholders)
    // ────────────────────────────────────────────────
    async function loadImages() {
      const statusEl = document.getElementById("status");

      try {
        statusEl.textContent = "Fetching from r/balls/new.json…";

        const res = await fetch(`https://www.reddit.com/r/${SUBREDDIT}/new.json?limit=${IMAGE_LIMIT}`, {
          headers: {
            "User-Agent": "balls-bouncer/1.0 (personal script; contact: none)"
          },
          cache: "no-store"
        });

        if (!res.ok) {
          throw new Error(`Reddit HTTP ${res.status} – probably rate-limited or blocked`);
        }

        const data = await res.json();
        const posts = data.data?.children || [];

        imagePool = posts
          .map(p => p.data)
          .filter(post => post.url)
          .map(post => {
            // Prefer direct i.redd.it links
            let url = post.url;
            // Some posts have preview images
            if (post.preview?.images?.[0]?.source?.url) {
              url = post.preview.images[0].source.url.replace(/&amp;/g, "&");
            }
            return url;
          })
          .filter(url =>
            url.match(/\.jpg$|\.jpeg$|\.png$|\.webp$/i) &&
            url.includes("i.redd.it")               // highest chance of direct image
          );

        statusEl.textContent = `Loaded ${imagePool.length} direct images from r/balls`;

        if (imagePool.length === 0) {
          statusEl.textContent += " (none were direct images – subreddit may use galleries/videos)";
        }

        console.log("Image URLs:", imagePool);
      } catch (err) {
        console.error("Fetch failed:", err);
        statusEl.textContent = "Failed to load images from Reddit. See console (CORS / 429 / auth issue likely).";
      }
    }

    // ────────────────────────────────────────────────
    // Multiply when closed (polling from main window – most reliable)
    // ────────────────────────────────────────────────
    function watchForClosures() {
      setInterval(() => {
        let closedCount = 0;
        for (const win of [...activePopups]) {
          if (win.closed) {
            activePopups.delete(win);
            closedCount++;
          }
        }
        if (closedCount > 0) {
          const howMany = closedCount * 3 + Math.floor(Math.random() * 3); // aggressive multiply
          for (let i = 0; i < howMany; i++) {
            setTimeout(spawnBouncingWindow, i * 220);
          }
        }
      }, 900);
    }

    // Backup: listen for child messages
    window.addEventListener('message', e => {
      if (e.data?.type === 'child_closing') {
        if (Math.random() < 0.8) {
          spawnBouncingWindow();
          setTimeout(spawnBouncingWindow, 300);
        }
      }
    });

    // Expose a function for children to call (if beforeunload works)
    window.spawnExtra = () => {
      if (Math.random() < 0.6) spawnBouncingWindow();
    };

    // ────────────────────────────────────────────────
    // Start everything
    // ────────────────────────────────────────────────
    (async () => {
      await loadImages();

      document.getElementById("launch").onclick = () => {
        if (imagePool.length === 0) {
          alert("No images loaded – can't launch without real r/balls pics.");
          return;
        }

        document.getElementById("start-screen").remove();

        // Launch initial wave
        for (let i = 0; i < 5; i++) {
          setTimeout(spawnBouncingWindow, i * 400);
        }

        watchForClosures();

        document.body.innerHTML = `<h1 style="color:#0f3; margin-top:45vh;">Good luck closing them…</h1>`;
      };

      // Extra chaos on random clicks after start
      document.addEventListener("click", () => {
        if (Math.random() < 0.22) spawnBouncingWindow();
      }, true);
    })();
  </script>
</body>
</html>
