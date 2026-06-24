"""
Singularity — Admin dashboard HTML (Fáze 2).

Samostatný modul, aby main.py zůstal přehledný.
Vrací self-contained HTML bez externích závislostí.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Singularity Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: system-ui, sans-serif; background: #0f0f13; color: #e2e8f0; padding: 24px; }
  h1 { font-size: 1.5rem; color: #a78bfa; margin-bottom: 4px; }
  .subtitle { color: #64748b; font-size: 0.85rem; margin-bottom: 24px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 20px; }
  .card { background: #1e1e2e; border: 1px solid #2d2d3d; border-radius: 10px; padding: 20px; }
  .card h2 { font-size: 0.95rem; color: #94a3b8; text-transform: uppercase;
              letter-spacing: .06em; margin-bottom: 14px; }
  table { width: 100%; border-collapse: collapse; font-size: 0.875rem; }
  th { text-align: left; color: #64748b; font-weight: 500; padding: 4px 8px 8px; }
  td { padding: 6px 8px; border-top: 1px solid #2d2d3d; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 0.75rem; }
  .ok  { background: #14532d; color: #4ade80; }
  .err { background: #450a0a; color: #f87171; }
  .warn{ background: #451a03; color: #fb923c; }
  .stat { display: flex; justify-content: space-between; margin-bottom: 8px; }
  .stat-val { font-weight: 600; color: #c4b5fd; }
  #strategy-form { display: flex; gap: 8px; margin-top: 14px; }
  select, button { background: #2d2d3d; color: #e2e8f0; border: 1px solid #3d3d4d;
                   border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 0.875rem; }
  button:hover { background: #3d3d4d; }
  .ts { color: #475569; font-size: 0.75rem; }
  .error-msg { color: #f87171; font-size: 0.8rem; margin-top: 6px; }
  pre { font-size: 0.78rem; color: #94a3b8; white-space: pre-wrap; word-break: break-all;
        max-height: 160px; overflow-y: auto; background: #12121a; padding: 10px;
        border-radius: 6px; margin-top: 8px; }
</style>
</head>
<body>
<h1>⬡ Singularity Dashboard</h1>
<p class="subtitle">Fáze 2 · auto-refresh 5s · <span id="ts" class="ts"></span></p>

<div class="grid">
  <!-- Providers -->
  <div class="card">
    <h2>Providers</h2>
    <div id="strategy-info" class="ts" style="margin-bottom:10px"></div>
    <table>
      <thead><tr>
        <th>Name</th><th>Status</th><th>Failures</th>
        <th>Cooldown</th><th>Cost/1k</th><th>Latency</th>
      </tr></thead>
      <tbody id="provider-rows"><tr><td colspan="6">načítám…</td></tr></tbody>
    </table>
    <div id="strategy-form">
      <select id="strategy-select">
        <option value="static">static</option>
        <option value="failover">failover</option>
        <option value="round_robin">round_robin</option>
        <option value="cost_optimized">cost_optimized</option>
        <option value="latency_optimized">latency_optimized</option>
        <option value="quality_first">quality_first</option>
      </select>
      <button onclick="setStrategy()">Změnit strategii</button>
    </div>
    <div id="strategy-msg" class="error-msg"></div>
  </div>

  <!-- Sessions -->
  <div class="card">
    <h2>Aktivní session</h2>
    <div id="session-stats">
      <div class="stat"><span>Uživatelé</span><span class="stat-val" id="user-count">–</span></div>
      <div class="stat"><span>Celkem turny</span><span class="stat-val" id="total-turns">–</span></div>
      <div class="stat"><span>Celkem náklady</span><span class="stat-val" id="total-cost">–</span></div>
    </div>
    <table style="margin-top:12px">
      <thead><tr><th>User</th><th>Turny</th><th>Náklady USD</th></tr></thead>
      <tbody id="session-rows"><tr><td colspan="3">načítám…</td></tr></tbody>
    </table>
  </div>

  <!-- Health -->
  <div class="card">
    <h2>Health check výsledky</h2>
    <div id="health-rows">načítám…</div>
    <button style="margin-top:12px" onclick="runHealth()">Spustit health check</button>
  </div>

  <!-- Metrics -->
  <div class="card" style="grid-column: 1 / -1">
    <h2>Prometheus metriky (raw)</h2>
    <pre id="metrics-raw">načítám…</pre>
  </div>
</div>

<script>
async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

async function loadProviders() {
  const data = await fetchJSON('/providers');
  document.getElementById('strategy-info').textContent =
    'Strategie: ' + data.strategy + ' · Gemini: ' + (data.gemini_enabled ? 'ano' : 'ne (degraded)');
  document.getElementById('strategy-select').value = data.strategy;
  const rows = data.providers.map(p => {
    const avail = p.available
      ? '<span class="badge ok">OK</span>'
      : '<span class="badge err">cooldown</span>';
    const cd = p.cooldown_remaining_s > 0 ? p.cooldown_remaining_s + 's' : '–';
    return `<tr>
      <td>${p.name}</td><td>${avail}</td>
      <td>${p.consecutive_failures}</td>
      <td>${cd}</td>
      <td>$${p.cost_per_1k}</td>
      <td>${p.typical_latency_ms}ms</td>
    </tr>`;
  }).join('');
  document.getElementById('provider-rows').innerHTML = rows || '<tr><td colspan="6">–</td></tr>';
}

async function loadSessions() {
  const data = await fetchJSON('/sessions');
  const users = data.users || [];
  document.getElementById('user-count').textContent = users.length;
  let totalTurns = 0, totalCost = 0;
  const details = await Promise.all(users.map(u => fetchJSON('/sessions/' + u)));
  const rows = details.map(s => {
    totalTurns += s.turn_count;
    totalCost += s.total_cost_usd;
    return `<tr><td>${s.user_id}</td><td>${s.turn_count}</td>
      <td>$${s.total_cost_usd.toFixed(6)}</td></tr>`;
  }).join('');
  document.getElementById('total-turns').textContent = totalTurns;
  document.getElementById('total-cost').textContent = '$' + totalCost.toFixed(6);
  document.getElementById('session-rows').innerHTML = rows || '<tr><td colspan="3">žádné session</td></tr>';
}

async function loadMetrics() {
  const r = await fetch('/metrics');
  const text = await r.text();
  const lines = text.split('\\n').filter(l => !l.startsWith('#') && l.trim());
  document.getElementById('metrics-raw').textContent =
    lines.length ? lines.join('\\n') : '(žádné záznamy)';
}

async function runHealth() {
  const el = document.getElementById('health-rows');
  el.textContent = 'Probíhá…';
  try {
    const data = await fetchJSON('/health/providers');
    el.innerHTML = Object.entries(data.results).map(([name, ok]) =>
      `<div class="stat"><span>${name}</span>
       <span class="badge ${ok ? 'ok' : 'err'}">${ok ? 'healthy' : 'down'}</span></div>`
    ).join('') || 'žádní provideři';
  } catch(e) {
    el.innerHTML = '<span class="error-msg">Endpoint /health/providers není dostupný</span>';
  }
}

async function setStrategy() {
  const strategy = document.getElementById('strategy-select').value;
  const msgEl = document.getElementById('strategy-msg');
  try {
    const r = await fetch('/router/strategy', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({strategy})
    });
    const data = await r.json();
    if (r.ok) {
      msgEl.style.color = '#4ade80';
      msgEl.textContent = '✓ Strategie změněna na ' + data.strategy;
    } else {
      msgEl.style.color = '#f87171';
      msgEl.textContent = data.detail || 'Chyba';
    }
  } catch(e) {
    msgEl.style.color = '#f87171';
    msgEl.textContent = String(e);
  }
  setTimeout(() => { msgEl.textContent = ''; }, 3000);
}

async function refresh() {
  document.getElementById('ts').textContent = new Date().toLocaleTimeString('cs');
  await Promise.allSettled([loadProviders(), loadSessions(), loadMetrics()]);
}

setInterval(refresh, 5000);
refresh();
</script>
</body>
</html>
"""


def get_dashboard_html() -> str:
    return DASHBOARD_HTML
