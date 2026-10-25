import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const STYLE = `
#acdev-output-browser{position:fixed;right:18px;bottom:18px;z-index:10000;font:14px sans-serif;color:#f4f4f5}
#acdev-output-browser button{background:#202127;color:inherit;border:1px solid #555;border-radius:8px;padding:10px 14px;cursor:pointer}
#acdev-output-modal{position:fixed;inset:4vh 4vw;z-index:10001;background:#15161a;border:1px solid #555;border-radius:12px;padding:18px;overflow:auto;box-shadow:0 12px 60px #000b}
#acdev-output-modal header{display:flex;align-items:center;justify-content:space-between;position:sticky;top:-18px;background:#15161a;padding:8px 0;z-index:1}
#acdev-output-items{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
.acdev-output-card{background:#202127;border-radius:10px;padding:10px;overflow:hidden}
.acdev-output-card video,.acdev-output-card audio{width:100%;display:block;background:#09090b;border-radius:6px}
.acdev-output-card .acdev-name{word-break:break-word;margin:8px 0;color:#eee}
.acdev-output-card a{color:#8dbdff}
`;

function viewUrl(item) {
  const q = new URLSearchParams({ filename: item.filename, subfolder: item.subfolder || "", type: item.type || "output" });
  return api.apiURL(`/view?${q.toString()}`);
}

function posterUrl(item) {
  const relative = `${item.subfolder ? `${item.subfolder}/` : ""}${item.filename}`;
  const digest = crypto.subtle.digest("SHA-256", new TextEncoder().encode(relative));
  return digest.then((hash) => {
    const hex = [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
    return viewUrl({ filename: `${hex}.jpg`, subfolder: ".ltx25-thumbnails", type: "output" });
  });
}

function collect(history) {
  const results = [];
  for (const [promptId, entry] of Object.entries(history || {})) {
    for (const [nodeId, output] of Object.entries(entry.outputs || {})) {
      for (const key of ["videos", "gifs", "audio", "images"]) {
        for (const file of output[key] || []) {
          const ext = (file.filename || "").split(".").pop().toLowerCase();
          const isVideo = key === "videos" || key === "gifs" || ["mp4", "webm", "mov"].includes(ext);
          const isAudio = key === "audio" || ["wav", "mp3", "flac", "m4a"].includes(ext);
          if (!isVideo && !isAudio) continue;
          results.push({ ...file, isVideo, promptId, nodeId });
        }
      }
    }
  }
  return results.slice(-200).reverse();
}

app.registerExtension({
  name: "ACDEV.LTX25.VideoOutputBrowser",
  async setup() {
    const style = document.createElement("style"); style.textContent = STYLE; document.head.append(style);
    const mount = document.createElement("div"); mount.id = "acdev-output-browser";
    const open = document.createElement("button"); open.textContent = "Videos & Audio"; mount.append(open); document.body.append(mount);
    let modal;
    const refresh = async () => {
      if (!modal) return;
      const grid = modal.querySelector("#acdev-output-items");
      grid.replaceChildren(Object.assign(document.createElement("p"), { textContent: "Loading recent outputs…" }));
      try {
        const response = await api.fetchApi("/history?max_items=100");
        if (!response.ok) throw new Error(`History request failed (${response.status})`);
        const items = collect(await response.json());
        if (!items.length) { grid.replaceChildren(Object.assign(document.createElement("p"), { textContent: "No recent video or audio outputs found." })); return; }
        const posters = await Promise.all(items.map((item) => (item.isVideo ? posterUrl(item) : null)));
        const cards = document.createDocumentFragment();
        items.forEach((item, index) => {
          const card = document.createElement("article"); card.className = "acdev-output-card";
          const media = document.createElement(item.isVideo ? "video" : "audio");
          // Posters stand in for the first frame, so nothing is fetched until a card is played.
          media.src = viewUrl(item); media.controls = true; media.preload = "none"; media.playsInline = true;
          if (item.isVideo) {
            media.muted = false;
            media.poster = posters[index];
            media.addEventListener("error", () => { media.removeAttribute("poster"); }, { once: true });
          }
          const name = document.createElement("div"); name.className = "acdev-name"; name.textContent = `${item.subfolder ? `${item.subfolder}/` : ""}${item.filename}`;
          const download = document.createElement("a"); download.href = media.src; download.download = item.filename; download.textContent = "Open / download original";
          card.append(media, name, download); cards.append(card);
        });
        grid.replaceChildren(cards);
      } catch (error) {
        grid.replaceChildren(Object.assign(document.createElement("p"), { textContent: `Could not load outputs: ${error.message}` }));
      }
    };
    const close = () => { modal?.remove(); modal = undefined; };
    open.addEventListener("click", async () => {
      if (modal) return;
      modal = document.createElement("section"); modal.id = "acdev-output-modal";
      const header = document.createElement("header");
      const title = document.createElement("strong"); title.textContent = "Recent Studio Outputs (latest 100 jobs)";
      const controls = document.createElement("div");
      const reload = document.createElement("button"); reload.textContent = "Refresh"; reload.onclick = refresh;
      const dismiss = document.createElement("button"); dismiss.textContent = "Close"; dismiss.onclick = close;
      controls.append(reload, dismiss); header.append(title, controls);
      const grid = document.createElement("div"); grid.id = "acdev-output-items"; modal.append(header, grid); document.body.append(modal);
      await refresh();
    });
    let timer;
    api.addEventListener("executed", () => { if (modal) { clearTimeout(timer); timer = setTimeout(refresh, 1200); } });
  }
});
