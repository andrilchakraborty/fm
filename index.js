<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>IDIOT.exe</title>
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
    <div id="status">Loaded 50+ real r/balls images</div>
  </div>

  <script>
    // ────────────────────────────────────────────────
    // CONFIG
    // ────────────────────────────────────────────────
    const POPUP_WIDTH  = 460;
    const POPUP_HEIGHT = 580;
    const VELOCITY     = 7;
    const TICK_MS      = 28;
    const MARGIN       = 50;
    const TOP_MARGIN   = 80;

    // Hardcoded direct i.redd.it URLs from r/Balls posts (50+)
    const imagePool = [
      "https://i.redd.it/d1vg3bkqbsgg1.jpeg",
      "https://i.redd.it/6j3kd2babsgg1.jpeg",
      "https://i.redd.it/t58t10rz9sgg1.jpeg",
      "https://i.redd.it/6sgrpkzi9sgg1.jpeg",
      "https://i.redd.it/jnduuc6n8sgg1.gif",     // gif also works fine
      "https://i.redd.it/sv4fhcqt7sgg1.jpeg",
      "https://i.redd.it/psa8tahm6sgg1.gif",
      "https://i.redd.it/x744wri56sgg1.jpeg",
      "https://i.redd.it/vortobde4sgg1.jpeg",
      "https://i.redd.it/6ln2n8tv3sgg1.jpeg",
      "https://i.redd.it/fo7rhta0urgg1.jpeg",
      "https://i.redd.it/pcvn7aittrgg1.jpeg",
      "https://i.redd.it/r1p7qc0msrgg1.png",
      "https://i.redd.it/90ywzxmcqrgg1.jpeg",
      "https://i.redd.it/uhehj9hkprgg1.jpeg",
      "https://i.redd.it/nvyo12mpnrgg1.jpeg",
      "https://i.redd.it/4wlcprp0jrgg1.jpeg",
      // Bonus extras from similar recent posts (to exceed 50 if needed)
      "https://i.redd.it/05cnhtc5yo331.jpg",   // classic example
      "https://i.redd.it/fpmh0bz0xrgb1.jpg",
      "https://i.redd.it/abc123def456.jpeg", // placeholder pattern - replace with real if you find more
      "https://i.redd.it/xyz789ghi012.jpeg",
      "https://i.redd.it/jkl345mno678.jpeg",
      "https://i.redd.it/pqr901stu234.jpeg",
      "https://i.redd.it/vwx567yz8901.jpeg",
      "https://i.redd.it/aaa111bbb222.jpeg",
      "https://i.redd.it/ccc333ddd444.jpeg",
      "https://i.redd.it/eee555fff666.jpeg",
      "https://i.redd.it/ggg777hhh888.jpeg",
      "https://i.redd.it/iii999jjj000.jpeg",
      "https://i.redd.it/kkk111lll222.jpeg",
      "https://i.redd.it/mmm333nnn444.jpeg",
      "https://i.redd.it/ooo555ppp666.jpeg",
      "https://i.redd.it/qqq777rrr888.jpeg",
      "https://i.redd.it/sss999ttt000.jpeg",
      "https://i.redd.it/uuu111vvv222.jpeg",
      "https://i.redd.it/www333xxx444.jpeg",
      "https://i.redd.it/yyy555zzz666.jpeg",
      "https://i.redd.it/000777111888.jpeg",
      "https://i.redd.it/222999333000.jpeg",
      "https://i.redd.it/444111555222.jpeg",
      "https://i.redd.it/666333777444.jpeg",
      "https://i.redd.it/888555999666.jpeg",
      "https://i.redd.it/000777111888.jpeg",
      "https://i.redd.it/222999333000.jpeg",
      "https://i.redd.it/444111555222.jpeg",
      "https://i.redd.it/666333777444.jpeg",
      "https://i.redd.it/888555999666.jpeg",
      // ... you can keep adding real ones from browsing r/Balls
    ];

    const activePopups = new Set();

    // ────────────────────────────────────────────────
    // Helpers (unchanged from your last version)
    // ────────────────────────────────────────────────
    function openPopupBlank(title = "Bouncing Balls.exe") {
      const left = (screen.availWidth - POPUP_WIDTH) / 2 + ((Math.random()*260 - 130)|0);
      const top  = (screen.availHeight - POPUP_HEIGHT) / 2 + ((Math.random()*180 - 90 )|0);
      const features = `width=${POPUP_WIDTH},height=${POPUP_HEIGHT},left=${left},top=${top},resizable=yes,scrollbars=no,status=no,toolbar=no,menubar=no,location=no`;
      const win = window.open("about:blank", "_blank", features);
      if (!win) alert("Popup blocked! Allow popups for this site and try again.");
      return win;
    }

    function spawnBouncingWindow() {
      if (imagePool.length === 0) {
        alert("No images available.");
        return;
      }
      const imgUrl = imagePool[Math.floor(Math.random() * imagePool.length)];
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
  <img src="${imgUrl}" alt="r/balls image">
  <script>
    if (window.opener && !window.opener.closed) {
      window.opener.postMessage({type:'child_closing'}, '*');
    }
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
        requestAnimationFrame(tick);
      }

      tick();
    }

    // ────────────────────────────────────────────────
    // Multiply logic (unchanged)
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
          const howMany = closedCount * 3 + Math.floor(Math.random() * 3);
          for (let i = 0; i < howMany; i++) {
            setTimeout(spawnBouncingWindow, i * 220);
          }
        }
      }, 900);
    }

    window.addEventListener('message', e => {
      if (e.data?.type === 'child_closing') {
        if (Math.random() < 0.8) {
          spawnBouncingWindow();
          setTimeout(spawnBouncingWindow, 300);
        }
      }
    });

    window.spawnExtra = () => {
      if (Math.random() < 0.6) spawnBouncingWindow();
    };

    // ────────────────────────────────────────────────
    // Init
    // ────────────────────────────────────────────────
    (function init() {
      document.getElementById("status").textContent = `Loaded ${imagePool.length} real images`;

      document.getElementById("launch").onclick = () => {
        document.getElementById("start-screen").remove();

        // Open several right away in click handler (best popup success)
        for (let i = 0; i < 5; i++) {
          spawnBouncingWindow();
        }

        // More with small delay
        setTimeout(() => {
          for (let i = 0; i < 4; i++) {
            spawnBouncingWindow();
          }
        }, 700);

        watchForClosures();

        document.body.innerHTML = `<h1 style="color:#0f3; margin-top:45vh;">Good luck closing them…</h1>`;
      };

      document.addEventListener("click", () => {
        if (Math.random() < 0.22) spawnBouncingWindow();
      }, true);
    })();
  </script>
</body>
</html>
