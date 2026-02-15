const api = require('./fpl-api');
const db = require('./database');

let syncInProgress = false;
let syncLog = [];

function log(msg) {
  const entry = `[${new Date().toISOString()}] ${msg}`;
  syncLog.push(entry);
  console.log(entry);
}

function getSyncStatus() {
  return {
    inProgress: syncInProgress,
    lastSync: db.getMeta('last_sync_time'),
    lastSyncedEvent: db.getLastSyncedEvent(),
    leagueId: db.getMeta('league_id'),
    log: syncLog.slice(-50),
  };
}

async function syncAll(leagueId) {
  if (syncInProgress) {
    throw new Error('Sync already in progress');
  }

  syncInProgress = true;
  syncLog = [];

  try {
    db.setMeta('league_id', leagueId);
    const lastSyncedEvent = db.getLastSyncedEvent();

    // 1. Fetch bootstrap-static for player data
    log('Fetching player data...');
    const bootstrap = await api.getBootstrapStatic();
    const elements = bootstrap.elements || [];
    const elementTypes = bootstrap.element_types || [];

    log(`Syncing ${elements.length} players...`);
    for (const el of elements) {
      db.upsertPlayer({
        id: el.id,
        web_name: el.web_name || '',
        first_name: el.first_name || '',
        second_name: el.second_name || '',
        team: el.team || 0,
        position: el.element_type || 0,
        total_points: el.total_points || 0,
        goals_scored: el.goals_scored || 0,
        assists: el.assists || 0,
        clean_sheets: el.clean_sheets || 0,
        minutes: el.minutes || 0,
        form: parseFloat(el.form) || 0,
        ict_index: parseFloat(el.ict_index) || 0,
        expected_goals: parseFloat(el.expected_goals) || 0,
        expected_assists: parseFloat(el.expected_assists) || 0,
        draft_rank: el.draft_rank || 0,
        status: el.status || 'a',
      });
    }
    log('Players synced.');

    // 2. Get current gameweek
    log('Fetching game state...');
    const game = await api.getGame();
    const currentEvent = game.current_event || 0;
    log(`Current gameweek: ${currentEvent}`);

    // 3. Fetch league details
    log('Fetching league details...');
    const league = await api.getLeagueDetails(leagueId);

    // Sync managers from standings
    const standings = league.standings || [];
    log(`Syncing ${standings.length} managers...`);
    for (const s of standings) {
      db.upsertManager({
        id: s.league_entry,
        name: s.entry_name || '',
        player_name: s.player_name || '',
        points_total: s.total || 0,
        wins: s.matches_won || 0,
        draws: s.matches_drawn || 0,
        losses: s.matches_lost || 0,
        points_for: s.points_for || 0,
        points_against: s.points_against || 0,
      });
    }
    log('Managers synced.');

    // Sync H2H matches
    log('Syncing H2H matches...');
    db.clearH2hMatches();
    const matches = league.matches || [];
    for (const m of matches) {
      if (m.finished) {
        let winnerId = null;
        if (m.league_entry_1_points > m.league_entry_2_points) {
          winnerId = m.league_entry_1;
        } else if (m.league_entry_2_points > m.league_entry_1_points) {
          winnerId = m.league_entry_2;
        }
        db.insertH2hMatch({
          event: m.event,
          manager_1_id: m.league_entry_1,
          manager_2_id: m.league_entry_2,
          manager_1_points: m.league_entry_1_points,
          manager_2_points: m.league_entry_2_points,
          winner_id: winnerId,
        });
      }
    }
    log(`${matches.filter(m => m.finished).length} H2H matches synced.`);

    // 4. Fetch each manager's history
    const managers = db.getAllManagers();
    for (const mgr of managers) {
      log(`Fetching history for ${mgr.player_name} (${mgr.id})...`);
      try {
        const history = await api.getEntryHistory(mgr.id);
        const historyEntries = history.history || [];
        for (const h of historyEntries) {
          db.upsertGameweekScore({
            manager_id: mgr.id,
            event: h.event,
            points: h.points,
            bench_points: h.points_on_bench || 0,
            total_points: h.total_points,
          });
        }
      } catch (err) {
        log(`Warning: Could not fetch history for manager ${mgr.id}: ${err.message}`);
      }
    }
    log('Gameweek histories synced.');

    // 5. Fetch team picks for new gameweeks
    const startEvent = lastSyncedEvent + 1;
    if (startEvent <= currentEvent) {
      log(`Fetching team picks for GW ${startEvent} to ${currentEvent}...`);
      for (const mgr of managers) {
        for (let gw = startEvent; gw <= currentEvent; gw++) {
          try {
            const picks = await api.getEntryEvent(mgr.id, gw);
            const picksList = picks.picks || [];
            for (const p of picksList) {
              db.upsertTeamPick({
                manager_id: mgr.id,
                event: gw,
                player_id: p.element,
                position: p.position,
                is_captain: p.is_captain ? 1 : 0,
                multiplier: p.multiplier || 1,
              });
            }
          } catch (err) {
            log(`Warning: Could not fetch picks for manager ${mgr.id} GW${gw}: ${err.message}`);
          }
        }
      }
      log('Team picks synced.');
    } else {
      log('Team picks already up to date.');
    }

    // 6. Fetch draft picks
    log('Fetching draft picks...');
    try {
      const draft = await api.getDraftChoices(leagueId);
      const choices = draft.choices || [];
      if (choices.length > 0) {
        db.clearDraftPicks();
        for (const c of choices) {
          db.insertDraftPick({
            round: c.round,
            pick: c.pick,
            manager_id: c.league_entry,
            player_id: c.element,
            was_auto: c.was_auto ? 1 : 0,
          });
        }
        log(`${choices.length} draft picks synced.`);
      }
    } catch (err) {
      log(`Warning: Could not fetch draft picks: ${err.message}`);
    }

    // 7. Fetch transactions
    log('Fetching transactions...');
    try {
      const txData = await api.getTransactions(leagueId);
      const txList = txData.transactions || txData || [];
      if (Array.isArray(txList) && txList.length > 0) {
        db.clearTransactions();
        for (const t of txList) {
          db.insertTransaction({
            manager_id: t.entry,
            event: t.event || 0,
            player_in_id: t.element_in,
            player_out_id: t.element_out,
            kind: t.kind || '',
            result: t.result || '',
            added: t.added || '',
          });
        }
        log(`${txList.length} transactions synced.`);
      }
    } catch (err) {
      log(`Warning: Could not fetch transactions: ${err.message}`);
    }

    // Update sync metadata
    if (currentEvent > 0) {
      db.setLastSyncedEvent(currentEvent);
    }
    db.setMeta('last_sync_time', new Date().toISOString());

    log('Sync complete!');
  } catch (err) {
    log(`Sync error: ${err.message}`);
    throw err;
  } finally {
    syncInProgress = false;
  }
}

module.exports = {
  syncAll,
  getSyncStatus,
};
