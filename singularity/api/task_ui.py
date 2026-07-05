"""
Jednoduché webové rozhraní pro pokládání tasků (`GET /ui`).

Stránka je servírovaná přímo aplikací (stejný vzor jako `api/dashboard.py`),
takže formulář odesílá `fetch("/task")` na **stejnou originu** — žádné CORS ani
CSP problémy. Vše je self-contained (inline CSS/JS, žádné externí zdroje).
"""

from __future__ import annotations

_HTML = """<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Singularity — Zadat task</title>
<style>
  :root{
    --bg:#eef1f7;--panel:#fff;--panel-2:#f4f6fb;--border:#dbe1ed;--border-soft:#e8ecf4;
    --text:#152038;--muted:#5b657a;--faint:#8a93a6;--accent:#0d8aa8;--accent-ink:#fff;
    --ok:#12925e;--crit:#d23a52;--warn:#a9670a;
    --mono:ui-monospace,"SF Mono","JetBrains Mono",Menlo,Consolas,monospace;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    --shadow:0 1px 2px rgba(20,30,60,.06),0 8px 24px rgba(20,30,60,.06);
  }
  @media (prefers-color-scheme:dark){
    :root{
      --bg:#0c1120;--panel:#141b2b;--panel-2:#1a2233;--border:#29334e;--border-soft:#212a42;
      --text:#e4e9f3;--muted:#8f99b1;--faint:#667088;--accent:#41c9e8;--accent-ink:#052632;
      --ok:#35c88a;--crit:#f2778a;--warn:#e0a742;
      --shadow:0 1px 2px rgba(0,0,0,.3),0 12px 30px rgba(0,0,0,.28);
    }
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.5;
    -webkit-font-smoothing:antialiased}
  .wrap{max-width:760px;margin:0 auto;padding:24px 20px 60px}
  header{display:flex;align-items:center;gap:12px;margin-bottom:6px}
  .mark{width:32px;height:32px;flex:0 0 auto}
  h1{font-size:16px;letter-spacing:.14em;text-transform:uppercase;margin:0;font-weight:700}
  .sub{font-size:12px;color:var(--muted)}
  .card{background:var(--panel);border:1px solid var(--border);border-radius:14px;
    box-shadow:var(--shadow);padding:20px;margin-top:18px}
  label{display:block;font-size:11px;letter-spacing:.07em;text-transform:uppercase;
    color:var(--faint);margin:0 0 6px}
  textarea,input,select{width:100%;font-family:var(--sans);font-size:14px;color:var(--text);
    background:var(--panel-2);border:1px solid var(--border);border-radius:10px;padding:11px 13px}
  textarea{min-height:120px;resize:vertical;line-height:1.5}
  textarea:focus,input:focus,select:focus{outline:2px solid var(--accent);outline-offset:1px;
    border-color:var(--accent)}
  .row{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px}
  .row>div{flex:1 1 160px}
  .field{margin-top:14px}
  .checkbox{display:flex;align-items:center;gap:9px;margin-top:14px;font-size:13.5px;color:var(--muted)}
  .checkbox input{width:auto}
  .actions{display:flex;align-items:center;gap:12px;margin-top:18px;flex-wrap:wrap}
  button.submit{background:var(--accent);color:var(--accent-ink);border:0;border-radius:10px;
    height:44px;padding:0 22px;font-size:14px;font-weight:700;cursor:pointer;letter-spacing:.02em}
  button.submit:disabled{opacity:.55;cursor:not-allowed}
  .hint{font-size:12px;color:var(--faint)}
  .adv summary{cursor:pointer;font-size:12.5px;color:var(--muted);margin-top:16px;
    list-style:none;user-select:none}
  .adv summary::-webkit-details-marker{display:none}
  .adv summary::before{content:"▸ ";color:var(--faint)}
  .adv[open] summary::before{content:"▾ "}
  .result{margin-top:18px}
  .status{display:flex;align-items:center;gap:9px;font-size:13px;margin-bottom:10px}
  .dot{width:9px;height:9px;border-radius:50%}
  .dot.ok{background:var(--ok)} .dot.err{background:var(--crit)} .dot.run{background:var(--warn)}
  .spin{width:15px;height:15px;border:2px solid var(--border);border-top-color:var(--accent);
    border-radius:50%;animation:spin .7s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
  @media (prefers-reduced-motion:reduce){.spin{animation:none}}
  .answer{background:var(--panel-2);border:1px solid var(--border);border-radius:10px;
    padding:14px 16px;white-space:pre-wrap;word-wrap:break-word;font-size:14.5px}
  .answer.err{border-color:var(--crit);color:var(--crit)}
  .dlabel{font-size:10.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--faint);
    margin:16px 0 6px}
  pre{margin:0;background:var(--bg);border:1px solid var(--border);border-radius:9px;
    padding:11px 13px;overflow-x:auto;font-family:var(--mono);font-size:12.5px;line-height:1.5}
  .meta{font-size:12px;color:var(--muted);margin-top:10px;font-family:var(--mono)}
  a{color:var(--accent)}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <svg class="mark" viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <circle cx="20" cy="20" r="18.5" stroke="var(--accent)" stroke-width="1.2" opacity=".45"/>
      <circle cx="20" cy="20" r="12" stroke="var(--accent)" stroke-width="1.2" opacity=".7"/>
      <circle cx="20" cy="20" r="5.5" stroke="var(--accent)" stroke-width="1.4"/>
      <circle cx="20" cy="20" r="2.4" fill="var(--accent)"/>
    </svg>
    <div>
      <h1>Singularity</h1>
      <div class="sub">Zadat task &middot; kognitivní smyčka na <code>POST /task</code></div>
    </div>
  </header>

  <form class="card" id="form">
    <label for="task">Task</label>
    <textarea id="task" placeholder="Napiš, co má Singularity udělat… např. „Vysvětli kvantové provázání ve dvou větách."" required></textarea>

    <div class="row">
      <div>
        <label for="user_id">User ID</label>
        <input id="user_id" type="text" value="default" autocomplete="off">
      </div>
      <div>
        <label for="force_provider">Provider</label>
        <select id="force_provider">
          <option value="">Auto (router rozhodne)</option>
          <option value="claude">claude</option>
          <option value="gemini">gemini</option>
        </select>
      </div>
    </div>

    <details class="adv">
      <summary>Rozšířené</summary>
      <div class="field">
        <label for="api_key">X-API-Key (jen když server běží s require_api_key)</label>
        <input id="api_key" type="password" placeholder="volitelné" autocomplete="off">
      </div>
      <div class="field">
        <label for="base">Base URL (prázdné = stejná origin)</label>
        <input id="base" type="text" placeholder="např. http://localhost:8001" autocomplete="off" spellcheck="false">
      </div>
      <label class="checkbox"><input id="approved" type="checkbox"> Předschváleno (přeskočí human-approval u rizikových tasků)</label>
    </details>

    <div class="actions">
      <button class="submit" id="send" type="submit">Odeslat task</button>
      <span class="hint">Reálný task přes LLM může trvat i desítky sekund.</span>
    </div>
  </form>

  <div class="result" id="result" hidden></div>
</div>

<script>
const $=id=>document.getElementById(id);
const form=$("form"), sendBtn=$("send"), resultEl=$("result");

function esc(s){return String(s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));}

function setBusy(b){
  sendBtn.disabled=b;
  sendBtn.textContent=b?"Odesílám…":"Odeslat task";
}

function showRunning(){
  resultEl.hidden=false;
  resultEl.innerHTML=`<div class="card"><div class="status">
    <span class="spin"></span><span>Zpracovávám task…</span></div></div>`;
}

function showError(msg){
  resultEl.hidden=false;
  resultEl.innerHTML=`<div class="card">
    <div class="status"><span class="dot err"></span><b>Chyba</b></div>
    <div class="answer err">${esc(msg)}</div></div>`;
}

function showResult(data){
  const pl=data.provider_log||{};
  const es=data.eval_scores||{};
  const plHtml=Object.keys(pl).length
    ? `<div class="dlabel">Provider log (který model dělal který krok)</div><pre>${esc(JSON.stringify(pl,null,2))}</pre>` : "";
  const esHtml=Object.keys(es).length
    ? `<div class="dlabel">Eval scores</div><pre>${esc(JSON.stringify(es,null,2))}</pre>` : "";
  resultEl.hidden=false;
  resultEl.innerHTML=`<div class="card">
    <div class="status"><span class="dot ok"></span><b>Hotovo</b></div>
    <div class="answer">${esc(data.response||"(prázdná odpověď)")}</div>
    ${plHtml}${esHtml}
    <div class="meta">session_id: ${esc(data.session_id||"—")}</div>
  </div>`;
}

form.addEventListener("submit", async (e)=>{
  e.preventDefault();
  const task=$("task").value.trim();
  if(!task) return;
  const base=$("base").value.trim().replace(/\\/$/,"");
  const key=$("api_key").value.trim();
  const payload={
    task,
    user_id: $("user_id").value.trim()||"default",
    force_provider: $("force_provider").value,
    approved: $("approved").checked,
  };
  const headers={"Content-Type":"application/json"};
  if(key) headers["X-API-Key"]=key;

  setBusy(true); showRunning();
  try{
    const r=await fetch(base+"/task",{method:"POST",headers,body:JSON.stringify(payload)});
    let body; const ct=r.headers.get("content-type")||"";
    body= ct.includes("application/json") ? await r.json() : await r.text();
    if(!r.ok){
      const detail=(body && typeof body==="object" && "detail" in body) ? body.detail : body;
      showError(`HTTP ${r.status} — ${typeof detail==="string"?detail:JSON.stringify(detail)}`);
    }else{
      showResult(body);
    }
  }catch(err){
    showError("Nepodařilo se spojit se serverem: "+err.message+
      "\\n\\nBěží aplikace? Zkus otevřít /health, nebo v Rozšířeném nastav Base URL.");
  }finally{
    setBusy(false);
  }
});
</script>
</body>
</html>
"""


def get_task_ui_html() -> str:
    """Vrátí HTML jednoduchého rozhraní pro zadávání tasků."""
    return _HTML
