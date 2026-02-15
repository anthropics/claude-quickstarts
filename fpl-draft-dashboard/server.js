const express = require('express');
const path = require('path');
const db = require('./src/database');
const sync = require('./src/sync');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// --- API Routes ---

// League info + standings
app.get('/api/league', (req, res) => {
  try {
    const managers = db.getAllManagers();
    const leagueId = db.getMeta('league_id');
    res.json({ leagueId, managers });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// All managers with stats
app.get('/api/managers', (req, res) => {
  try {
    res.json(db.getAllManagers());
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Full H2H matrix
app.get('/api/h2h', (req, res) => {
  try {
    const matches = db.getH2hMatches();
    const managers = db.getAllManagers();

    // Build matrix: for each pair, compute W-D-L from manager_1's perspective
    const matrix = {};
    for (const m of managers) {
      matrix[m.id] = {};
      for (const m2 of managers) {
        if (m.id !== m2.id) {
          matrix[m.id][m2.id] = { wins: 0, draws: 0, losses: 0, pf: 0, pa: 0 };
        }
      }
    }

    for (const match of matches) {
      const { manager_1_id, manager_2_id, manager_1_points, manager_2_points, winner_id } = match;

      if (matrix[manager_1_id] && matrix[manager_1_id][manager_2_id]) {
        matrix[manager_1_id][manager_2_id].pf += manager_1_points;
        matrix[manager_1_id][manager_2_id].pa += manager_2_points;
        if (winner_id === manager_1_id) matrix[manager_1_id][manager_2_id].wins++;
        else if (winner_id === manager_2_id) matrix[manager_1_id][manager_2_id].losses++;
        else matrix[manager_1_id][manager_2_id].draws++;
      }

      if (matrix[manager_2_id] && matrix[manager_2_id][manager_1_id]) {
        matrix[manager_2_id][manager_1_id].pf += manager_2_points;
        matrix[manager_2_id][manager_1_id].pa += manager_1_points;
        if (winner_id === manager_2_id) matrix[manager_2_id][manager_1_id].wins++;
        else if (winner_id === manager_1_id) matrix[manager_2_id][manager_1_id].losses++;
        else matrix[manager_2_id][manager_1_id].draws++;
      }
    }

    res.json({ managers, matrix });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// H2H between two specific managers
app.get('/api/h2h/:id1/:id2', (req, res) => {
  try {
    const id1 = parseInt(req.params.id1, 10);
    const id2 = parseInt(req.params.id2, 10);
    const matches = db.getH2hBetween(id1, id2);
    res.json(matches);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// All gameweek scores
app.get('/api/gameweeks', (req, res) => {
  try {
    res.json(db.getGameweekScores());
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Team ratings per manager
app.get('/api/team-ratings', (req, res) => {
  try {
    const managers = db.getAllManagers();
    const picks = db.getLatestTeamPicks();
    const players = db.getAllPlayers();
    const playerMap = {};
    for (const p of players) playerMap[p.id] = p;

    const ratings = managers.map((mgr) => {
      const mgrPicks = picks.filter((p) => p.manager_id === mgr.id);
      const squad = mgrPicks.map((p) => playerMap[p.player_id]).filter(Boolean);

      const totalPoints = squad.reduce((s, p) => s + (p.total_points || 0), 0);
      const avgForm = squad.length > 0
        ? squad.reduce((s, p) => s + (p.form || 0), 0) / squad.length
        : 0;
      const avgIct = squad.length > 0
        ? squad.reduce((s, p) => s + (p.ict_index || 0), 0) / squad.length
        : 0;

      // Position breakdown
      const byPos = { 1: [], 2: [], 3: [], 4: [] };
      for (const p of squad) {
        if (byPos[p.position]) byPos[p.position].push(p);
      }

      const posStrength = {};
      for (const [pos, posPlayers] of Object.entries(byPos)) {
        posStrength[pos] = posPlayers.reduce((s, p) => s + (p.total_points || 0), 0);
      }

      return {
        manager: mgr,
        totalPoints,
        avgForm: Math.round(avgForm * 10) / 10,
        avgIct: Math.round(avgIct * 10) / 10,
        positionStrength: posStrength,
        squad: squad.map((p) => ({
          id: p.id,
          web_name: p.web_name,
          position: p.position,
          total_points: p.total_points,
          form: p.form,
          ict_index: p.ict_index,
        })),
      };
    });

    res.json(ratings);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// All players
app.get('/api/players', (req, res) => {
  try {
    const players = db.getAllPlayers();
    // Add ownership info
    const picks = db.getLatestTeamPicks();
    const managers = db.getAllManagers();
    const mgrMap = {};
    for (const m of managers) mgrMap[m.id] = m;

    const ownerMap = {};
    for (const p of picks) {
      ownerMap[p.player_id] = mgrMap[p.manager_id] || null;
    }

    const enriched = players.map((p) => ({
      ...p,
      owner: ownerMap[p.id] ? { id: ownerMap[p.id].id, name: ownerMap[p.id].player_name } : null,
    }));

    res.json(enriched);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Draft picks
app.get('/api/draft', (req, res) => {
  try {
    const picks = db.getDraftPicks();
    const players = db.getAllPlayers();
    const managers = db.getAllManagers();

    const playerMap = {};
    for (const p of players) playerMap[p.id] = p;
    const mgrMap = {};
    for (const m of managers) mgrMap[m.id] = m;

    const enriched = picks.map((dp) => ({
      ...dp,
      player: playerMap[dp.player_id] ? {
        web_name: playerMap[dp.player_id].web_name,
        total_points: playerMap[dp.player_id].total_points,
        position: playerMap[dp.player_id].position,
      } : null,
      manager: mgrMap[dp.manager_id] ? {
        name: mgrMap[dp.manager_id].name,
        player_name: mgrMap[dp.manager_id].player_name,
      } : null,
    }));

    res.json(enriched);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Transactions
app.get('/api/transactions', (req, res) => {
  try {
    const txs = db.getTransactions();
    const players = db.getAllPlayers();
    const managers = db.getAllManagers();

    const playerMap = {};
    for (const p of players) playerMap[p.id] = p;
    const mgrMap = {};
    for (const m of managers) mgrMap[m.id] = m;

    const enriched = txs.map((t) => ({
      ...t,
      player_in: playerMap[t.player_in_id] ? { web_name: playerMap[t.player_in_id].web_name } : null,
      player_out: playerMap[t.player_out_id] ? { web_name: playerMap[t.player_out_id].web_name } : null,
      manager: mgrMap[t.manager_id] ? {
        name: mgrMap[t.manager_id].name,
        player_name: mgrMap[t.manager_id].player_name,
      } : null,
    }));

    res.json(enriched);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Trigger sync
app.post('/api/sync', async (req, res) => {
  const { leagueId } = req.body;
  if (!leagueId) {
    return res.status(400).json({ error: 'leagueId is required' });
  }

  try {
    // Start sync in background and respond immediately
    res.json({ message: 'Sync started', leagueId });
    await sync.syncAll(leagueId);
  } catch (err) {
    console.error('Sync error:', err);
  }
});

// Sync status
app.get('/api/sync/status', (req, res) => {
  try {
    res.json(sync.getSyncStatus());
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Serve dashboard for all non-API routes
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`FPL Draft Dashboard running at http://localhost:${PORT}`);
});
