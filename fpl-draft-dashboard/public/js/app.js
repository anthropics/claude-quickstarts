// FPL Draft Dashboard — Frontend Logic

const POS_LABELS = { 1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD' };
const POS_CLASSES = { 1: 'pos-gk', 2: 'pos-def', 3: 'pos-mid', 4: 'pos-fwd' };
const COLORS = [
  '#00ff87', '#e90052', '#00c8ff', '#f0c040', '#bf5af2',
  '#ff6b35', '#04e762', '#ff1493', '#32cd32', '#ffa500',
  '#00bfff', '#ff4500',
];

let allPlayers = [];
let allTransactions = [];
let managers = [];
let charts = {};

// --- Initialization ---

document.addEventListener('DOMContentLoaded', async () => {
  setupTabs();
  const status = await fetchJson('/api/sync/status');
  if (status && status.leagueId) {
    await loadDashboard();
  } else {
    showSetup();
  }
});

function showSetup() {
  document.getElementById('setup-modal').classList.remove('hidden');
  document.getElementById('dashboard').classList.add('hidden');
}

function setupTabs() {
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach((tc) => tc.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById('tab-' + tab.dataset.tab).classList.add('active');
    });
  });
}

// --- Sync ---

async function startSync() {
  const input = document.getElementById('league-id-input');
  const leagueId = input.value.trim();
  if (!leagueId) return;

  document.getElementById('sync-btn').disabled = true;
  document.getElementById('setup-modal').classList.add('hidden');
  document.getElementById('sync-overlay').classList.remove('hidden');

  try {
    await fetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ leagueId }),
    });

    // Poll sync status
    await pollSync();
  } catch (err) {
    showSyncError(err.message);
  }
}

async function resync() {
  const status = await fetchJson('/api/sync/status');
  if (!status || !status.leagueId) return;

  document.getElementById('sync-overlay').classList.remove('hidden');
  try {
    await fetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ leagueId: status.leagueId }),
    });
    await pollSync();
  } catch (err) {
    showSyncError(err.message);
  }
}

async function pollSync() {
  const logEl = document.getElementById('sync-log');
  const progressEl = document.getElementById('sync-progress');
  let progress = 10;

  const poll = async () => {
    const status = await fetchJson('/api/sync/status');
    if (status && status.log) {
      logEl.innerHTML = status.log.map((l) => `<div>${escapeHtml(l)}</div>`).join('');
      logEl.scrollTop = logEl.scrollHeight;
    }

    progress = Math.min(progress + 5, 95);
    progressEl.style.width = progress + '%';

    if (status && status.inProgress) {
      setTimeout(poll, 1500);
    } else {
      progressEl.style.width = '100%';
      setTimeout(async () => {
        document.getElementById('sync-overlay').classList.add('hidden');
        await loadDashboard();
      }, 500);
    }
  };

  setTimeout(poll, 2000);
}

function showSyncError(msg) {
  const el = document.getElementById('setup-status');
  el.textContent = 'Sync error: ' + msg;
  el.className = 'status-msg error';
  el.classList.remove('hidden');
  document.getElementById('sync-overlay').classList.add('hidden');
  document.getElementById('setup-modal').classList.remove('hidden');
  document.getElementById('sync-btn').disabled = false;
}

// --- Dashboard Loading ---

async function loadDashboard() {
  document.getElementById('setup-modal').classList.add('hidden');
  document.getElementById('dashboard').classList.remove('hidden');

  const status = await fetchJson('/api/sync/status');
  if (status && status.lastSync) {
    const d = new Date(status.lastSync);
    document.getElementById('last-sync').textContent = 'Last sync: ' + d.toLocaleString();
  }
  if (status && status.leagueId) {
    document.getElementById('league-info').textContent = 'League #' + status.leagueId;
  }

  // Load all data in parallel
  const [leagueData, h2hData, gameweeks, teamRatings, playersData, draftData, txData] =
    await Promise.all([
      fetchJson('/api/league'),
      fetchJson('/api/h2h'),
      fetchJson('/api/gameweeks'),
      fetchJson('/api/team-ratings'),
      fetchJson('/api/players'),
      fetchJson('/api/draft'),
      fetchJson('/api/transactions'),
    ]);

  managers = leagueData ? leagueData.managers || [] : [];
  allPlayers = playersData || [];
  allTransactions = txData || [];

  renderLeague(leagueData, gameweeks);
  renderH2H(h2hData);
  renderTeams(teamRatings);
  renderTrends(gameweeks, managers);
  renderPlayers(allPlayers);
  renderDraft(draftData);
  renderTransactions(allTransactions, managers);
}

// --- League Tab ---

function renderLeague(data, gameweeks) {
  if (!data || !data.managers) return;
  const mgrs = data.managers;

  // Standings
  const tbody = document.querySelector('#standings-table tbody');
  tbody.innerHTML = mgrs
    .sort((a, b) => b.points_total - a.points_total)
    .map((m, i) => `
      <tr>
        <td>${i + 1}</td>
        <td>${escapeHtml(m.player_name)}</td>
        <td>${escapeHtml(m.name)}</td>
        <td>${m.wins}</td>
        <td>${m.draws}</td>
        <td>${m.losses}</td>
        <td>${m.points_for}</td>
        <td>${m.points_against}</td>
        <td><strong>${m.points_total}</strong></td>
      </tr>
    `)
    .join('');

  // Season stats
  const statsEl = document.getElementById('season-stats');
  const gws = gameweeks || [];

  // Group by manager
  const byMgr = {};
  for (const g of gws) {
    if (!byMgr[g.manager_id]) byMgr[g.manager_id] = [];
    byMgr[g.manager_id].push(g);
  }

  const mgrMap = {};
  for (const m of mgrs) mgrMap[m.id] = m;

  // Highest GW score
  let highestGw = { points: 0 };
  for (const g of gws) {
    if (g.points > highestGw.points) highestGw = g;
  }

  // Most consistent (lowest std dev)
  let mostConsistent = { name: '-', stdDev: Infinity };
  for (const [mId, scores] of Object.entries(byMgr)) {
    if (scores.length < 2) continue;
    const pts = scores.map((s) => s.points);
    const mean = pts.reduce((a, b) => a + b, 0) / pts.length;
    const variance = pts.reduce((a, p) => a + (p - mean) ** 2, 0) / pts.length;
    const stdDev = Math.sqrt(variance);
    if (stdDev < mostConsistent.stdDev) {
      mostConsistent = { name: mgrMap[mId]?.player_name || mId, stdDev: Math.round(stdDev * 10) / 10 };
    }
  }

  // Biggest win margin
  let biggestWin = { margin: 0, desc: '-' };
  // We'd need H2H data here, but approximate from stats
  const topScorer = mgrs.reduce((best, m) => (m.points_for > (best?.points_for || 0) ? m : best), mgrs[0]);

  statsEl.innerHTML = `
    <div class="stat-card">
      <div class="stat-label">Highest GW Score</div>
      <div class="stat-value">${highestGw.points || '-'}</div>
      <div class="stat-sub">${mgrMap[highestGw.manager_id]?.player_name || ''} — GW${highestGw.event || ''}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Most Consistent</div>
      <div class="stat-value">${escapeHtml(mostConsistent.name)}</div>
      <div class="stat-sub">Std Dev: ${mostConsistent.stdDev}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Top Points Scorer</div>
      <div class="stat-value">${topScorer?.points_for || '-'}</div>
      <div class="stat-sub">${escapeHtml(topScorer?.player_name || '')}</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Managers</div>
      <div class="stat-value">${mgrs.length}</div>
      <div class="stat-sub">GWs played: ${new Set(gws.map(g => g.event)).size}</div>
    </div>
  `;
}

// --- H2H Tab ---

function renderH2H(data) {
  if (!data || !data.managers) return;
  const mgrs = data.managers;
  const matrix = data.matrix;
  const table = document.getElementById('h2h-matrix');

  let html = '<thead><tr><th></th>';
  for (const m of mgrs) {
    html += `<th>${escapeHtml(m.player_name)}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const m1 of mgrs) {
    html += `<tr><td><strong>${escapeHtml(m1.player_name)}</strong></td>`;
    for (const m2 of mgrs) {
      if (m1.id === m2.id) {
        html += '<td class="h2h-self">-</td>';
      } else {
        const rec = matrix[m1.id]?.[m2.id] || { wins: 0, draws: 0, losses: 0 };
        html += `<td class="h2h-cell" onclick="showH2hDetail(${m1.id}, ${m2.id})">
          <span class="h2h-record">
            <span class="win">${rec.wins}</span><span class="h2h-sep">-</span><span class="draw">${rec.draws}</span><span class="h2h-sep">-</span><span class="loss">${rec.losses}</span>
          </span>
        </td>`;
      }
    }
    html += '</tr>';
  }
  html += '</tbody>';
  table.innerHTML = html;
}

async function showH2hDetail(id1, id2) {
  const matches = await fetchJson(`/api/h2h/${id1}/${id2}`);
  if (!matches || !matches.length) return;

  const mgrMap = {};
  for (const m of managers) mgrMap[m.id] = m;

  const name1 = mgrMap[id1]?.player_name || id1;
  const name2 = mgrMap[id2]?.player_name || id2;

  document.getElementById('h2h-detail').classList.remove('hidden');
  document.getElementById('h2h-detail-title').textContent = `${name1} vs ${name2}`;
  document.getElementById('h2h-p1-name').textContent = name1;
  document.getElementById('h2h-p2-name').textContent = name2;

  const tbody = document.querySelector('#h2h-detail-table tbody');
  tbody.innerHTML = matches
    .map((m) => {
      // Normalize so id1 is always on the left
      let p1pts, p2pts;
      if (m.manager_1_id === id1) {
        p1pts = m.manager_1_points;
        p2pts = m.manager_2_points;
      } else {
        p1pts = m.manager_2_points;
        p2pts = m.manager_1_points;
      }
      let result;
      if (p1pts > p2pts) result = `<span class="win">Win</span>`;
      else if (p1pts < p2pts) result = `<span class="loss">Loss</span>`;
      else result = `<span class="draw">Draw</span>`;

      return `<tr>
        <td>GW${m.event}</td>
        <td>${p1pts}</td>
        <td>${p1pts} - ${p2pts}</td>
        <td>${p2pts}</td>
        <td>${result}</td>
      </tr>`;
    })
    .join('');
}

// --- Teams Tab ---

function renderTeams(ratings) {
  if (!ratings || !ratings.length) return;

  // Team ratings bar chart
  destroyChart('team-ratings-chart');
  const ctx1 = document.getElementById('team-ratings-chart').getContext('2d');
  charts['team-ratings-chart'] = new Chart(ctx1, {
    type: 'bar',
    data: {
      labels: ratings.map((r) => r.manager.player_name),
      datasets: [
        {
          label: 'Squad Total Points',
          data: ratings.map((r) => r.totalPoints),
          backgroundColor: COLORS.slice(0, ratings.length).map((c) => c + '88'),
          borderColor: COLORS.slice(0, ratings.length),
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { ticks: { color: '#a0a0b0' }, grid: { color: '#2a2a4a' } },
        x: { ticks: { color: '#a0a0b0' }, grid: { display: false } },
      },
    },
  });

  // Position strength stacked bar
  destroyChart('position-chart');
  const ctx2 = document.getElementById('position-chart').getContext('2d');
  charts['position-chart'] = new Chart(ctx2, {
    type: 'bar',
    data: {
      labels: ratings.map((r) => r.manager.player_name),
      datasets: [
        { label: 'GK', data: ratings.map((r) => r.positionStrength['1'] || 0), backgroundColor: '#f0c040' },
        { label: 'DEF', data: ratings.map((r) => r.positionStrength['2'] || 0), backgroundColor: '#00c8ff' },
        { label: 'MID', data: ratings.map((r) => r.positionStrength['3'] || 0), backgroundColor: '#00ff87' },
        { label: 'FWD', data: ratings.map((r) => r.positionStrength['4'] || 0), backgroundColor: '#e90052' },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#a0a0b0' } } },
      scales: {
        x: { stacked: true, ticks: { color: '#a0a0b0' }, grid: { display: false } },
        y: { stacked: true, ticks: { color: '#a0a0b0' }, grid: { color: '#2a2a4a' } },
      },
    },
  });

  // Squad lists
  const listsEl = document.getElementById('squad-lists');
  listsEl.innerHTML = '<div class="squad-grid">' +
    ratings.map((r) => `
      <div class="squad-card">
        <h4>${escapeHtml(r.manager.player_name)} — ${escapeHtml(r.manager.name)}</h4>
        <div style="margin-bottom:0.5rem;font-size:0.85rem;color:var(--text-secondary)">
          Avg Form: ${r.avgForm} | Avg ICT: ${r.avgIct} | Squad Pts: ${r.totalPoints}
        </div>
        <table>
          <thead><tr><th>Player</th><th>Pos</th><th>Pts</th><th>Form</th></tr></thead>
          <tbody>
            ${r.squad
              .sort((a, b) => a.position - b.position)
              .map((p) => `
                <tr>
                  <td>${escapeHtml(p.web_name)}</td>
                  <td><span class="pos-badge ${POS_CLASSES[p.position]}">${POS_LABELS[p.position]}</span></td>
                  <td>${p.total_points}</td>
                  <td>${p.form}</td>
                </tr>
              `).join('')}
          </tbody>
        </table>
      </div>
    `).join('') +
    '</div>';
}

// --- Trends Tab ---

function renderTrends(gameweeks, mgrs) {
  if (!gameweeks || !gameweeks.length || !mgrs || !mgrs.length) return;

  const mgrMap = {};
  for (const m of mgrs) mgrMap[m.id] = m;

  // Group scores by manager
  const byMgr = {};
  for (const g of gameweeks) {
    if (!byMgr[g.manager_id]) byMgr[g.manager_id] = [];
    byMgr[g.manager_id].push(g);
  }

  // Get all events
  const events = [...new Set(gameweeks.map((g) => g.event))].sort((a, b) => a - b);

  // Points per GW
  destroyChart('points-per-gw-chart');
  const ctx1 = document.getElementById('points-per-gw-chart').getContext('2d');
  const datasets1 = Object.entries(byMgr).map(([mId, scores], i) => ({
    label: mgrMap[mId]?.player_name || mId,
    data: events.map((e) => {
      const s = scores.find((sc) => sc.event === e);
      return s ? s.points : null;
    }),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length] + '22',
    tension: 0.3,
    pointRadius: 3,
  }));

  charts['points-per-gw-chart'] = new Chart(ctx1, {
    type: 'line',
    data: { labels: events.map((e) => 'GW' + e), datasets: datasets1 },
    options: chartOptions('Points'),
  });

  // Cumulative points
  destroyChart('cumulative-chart');
  const ctx2 = document.getElementById('cumulative-chart').getContext('2d');
  const datasets2 = Object.entries(byMgr).map(([mId, scores], i) => {
    const sorted = [...scores].sort((a, b) => a.event - b.event);
    let cumulative = 0;
    const data = events.map((e) => {
      const s = sorted.find((sc) => sc.event === e);
      if (s) cumulative += s.points;
      return cumulative;
    });
    return {
      label: mgrMap[mId]?.player_name || mId,
      data,
      borderColor: COLORS[i % COLORS.length],
      tension: 0.3,
      pointRadius: 2,
    };
  });

  charts['cumulative-chart'] = new Chart(ctx2, {
    type: 'line',
    data: { labels: events.map((e) => 'GW' + e), datasets: datasets2 },
    options: chartOptions('Cumulative Points'),
  });

  // Highs and lows per GW
  destroyChart('highs-lows-chart');
  const ctx3 = document.getElementById('highs-lows-chart').getContext('2d');
  const highs = events.map((e) => {
    const gwScores = gameweeks.filter((g) => g.event === e);
    return Math.max(...gwScores.map((g) => g.points));
  });
  const lows = events.map((e) => {
    const gwScores = gameweeks.filter((g) => g.event === e);
    return Math.min(...gwScores.map((g) => g.points));
  });

  charts['highs-lows-chart'] = new Chart(ctx3, {
    type: 'bar',
    data: {
      labels: events.map((e) => 'GW' + e),
      datasets: [
        { label: 'Highest', data: highs, backgroundColor: '#00ff8866', borderColor: '#00ff88', borderWidth: 1 },
        { label: 'Lowest', data: lows, backgroundColor: '#e9005266', borderColor: '#e90052', borderWidth: 1 },
      ],
    },
    options: chartOptions('Points'),
  });

  // Consistency
  destroyChart('consistency-chart');
  const ctx4 = document.getElementById('consistency-chart').getContext('2d');
  const consistencyData = Object.entries(byMgr).map(([mId, scores]) => {
    const pts = scores.map((s) => s.points);
    const mean = pts.reduce((a, b) => a + b, 0) / pts.length;
    const variance = pts.reduce((a, p) => a + (p - mean) ** 2, 0) / pts.length;
    return { name: mgrMap[mId]?.player_name || mId, stdDev: Math.round(Math.sqrt(variance) * 10) / 10 };
  }).sort((a, b) => a.stdDev - b.stdDev);

  charts['consistency-chart'] = new Chart(ctx4, {
    type: 'bar',
    data: {
      labels: consistencyData.map((c) => c.name),
      datasets: [{
        label: 'Std Deviation',
        data: consistencyData.map((c) => c.stdDev),
        backgroundColor: consistencyData.map((_, i) => COLORS[i % COLORS.length] + '88'),
        borderColor: consistencyData.map((_, i) => COLORS[i % COLORS.length]),
        borderWidth: 1,
      }],
    },
    options: {
      ...chartOptions('Std Dev'),
      indexAxis: 'y',
    },
  });
}

function chartOptions(yLabel) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: '#a0a0b0' } } },
    scales: {
      x: { ticks: { color: '#a0a0b0' }, grid: { color: '#2a2a4a' } },
      y: { title: { display: true, text: yLabel, color: '#a0a0b0' }, ticks: { color: '#a0a0b0' }, grid: { color: '#2a2a4a' } },
    },
  };
}

// --- Players Tab ---

function renderPlayers(players) {
  if (!players) return;
  allPlayers = players;
  filterPlayers();
}

function filterPlayers() {
  const search = (document.getElementById('player-search').value || '').toLowerCase();
  const posFilter = document.getElementById('player-pos-filter').value;
  const sortBy = document.getElementById('player-sort').value || 'total_points';

  let filtered = allPlayers.filter((p) => {
    if (search && !p.web_name.toLowerCase().includes(search) &&
        !(p.first_name || '').toLowerCase().includes(search) &&
        !(p.second_name || '').toLowerCase().includes(search)) return false;
    if (posFilter && p.position !== parseInt(posFilter)) return false;
    return true;
  });

  filtered.sort((a, b) => (b[sortBy] || 0) - (a[sortBy] || 0));

  const tbody = document.querySelector('#players-table tbody');
  tbody.innerHTML = filtered
    .slice(0, 200) // Limit for performance
    .map((p) => `
      <tr>
        <td>${escapeHtml(p.web_name)}</td>
        <td><span class="pos-badge ${POS_CLASSES[p.position]}">${POS_LABELS[p.position] || '?'}</span></td>
        <td>${p.total_points}</td>
        <td>${p.goals_scored}</td>
        <td>${p.assists}</td>
        <td>${p.clean_sheets}</td>
        <td>${p.ict_index}</td>
        <td>${p.form}</td>
        <td>${p.owner ? escapeHtml(p.owner.name) : '<span style="color:var(--text-muted)">Free</span>'}</td>
      </tr>
    `)
    .join('');
}

// --- Draft Tab ---

function renderDraft(picks) {
  if (!picks || !picks.length) return;

  const tbody = document.querySelector('#draft-table tbody');
  tbody.innerHTML = picks
    .map((dp) => `
      <tr>
        <td>${dp.round}</td>
        <td>${dp.pick}</td>
        <td>${dp.manager ? escapeHtml(dp.manager.player_name) : '-'}</td>
        <td>${dp.player ? escapeHtml(dp.player.web_name) : '-'}</td>
        <td>${dp.player ? `<span class="pos-badge ${POS_CLASSES[dp.player.position]}">${POS_LABELS[dp.player.position]}</span>` : '-'}</td>
        <td>${dp.player ? dp.player.total_points : '-'}</td>
        <td>${dp.was_auto ? 'Yes' : ''}</td>
      </tr>
    `)
    .join('');
}

// --- Transactions Tab ---

function renderTransactions(txs, mgrs) {
  if (!txs) return;
  allTransactions = txs;

  // Populate manager filter
  const select = document.getElementById('tx-manager-filter');
  const existingOpts = select.querySelectorAll('option:not(:first-child)');
  existingOpts.forEach((o) => o.remove());
  for (const m of mgrs) {
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.textContent = m.player_name;
    select.appendChild(opt);
  }

  filterTransactions();
}

function filterTransactions() {
  const mgrFilter = document.getElementById('tx-manager-filter').value;
  const typeFilter = document.getElementById('tx-type-filter').value;
  const resultFilter = document.getElementById('tx-result-filter').value;

  let filtered = allTransactions.filter((t) => {
    if (mgrFilter && t.manager_id !== parseInt(mgrFilter)) return false;
    if (typeFilter && t.kind !== typeFilter) return false;
    if (resultFilter && t.result !== resultFilter) return false;
    return true;
  });

  const tbody = document.querySelector('#transactions-table tbody');
  tbody.innerHTML = filtered
    .map((t) => {
      const typeBadge = t.kind === 'w'
        ? '<span class="tx-badge tx-waiver">Waiver</span>'
        : '<span class="tx-badge tx-free">Free Agent</span>';
      const resultBadge = t.result === 'a'
        ? '<span class="tx-badge tx-accepted">Accepted</span>'
        : '<span class="tx-badge tx-declined">Declined</span>';
      const date = t.added ? new Date(t.added).toLocaleDateString() : '-';

      return `<tr>
        <td>GW${t.event || '-'}</td>
        <td>${t.manager ? escapeHtml(t.manager.player_name) : '-'}</td>
        <td style="color:var(--accent)">${t.player_in ? escapeHtml(t.player_in.web_name) : '-'}</td>
        <td style="color:var(--accent-secondary)">${t.player_out ? escapeHtml(t.player_out.web_name) : '-'}</td>
        <td>${typeBadge}</td>
        <td>${resultBadge}</td>
        <td>${date}</td>
      </tr>`;
    })
    .join('');
}

// --- Utilities ---

async function fetchJson(url) {
  try {
    const res = await fetch(url);
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function destroyChart(id) {
  if (charts[id]) {
    charts[id].destroy();
    delete charts[id];
  }
}
