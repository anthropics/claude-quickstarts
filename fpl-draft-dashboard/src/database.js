const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

const DB_PATH = path.join(__dirname, '..', 'data', 'fpl-draft.db');

let db;

function getDb() {
  if (!db) {
    fs.mkdirSync(path.dirname(DB_PATH), { recursive: true });
    db = new Database(DB_PATH);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
    initSchema();
  }
  return db;
}

function initSchema() {
  const d = getDb();

  d.exec(`
    CREATE TABLE IF NOT EXISTS metadata (
      key TEXT PRIMARY KEY,
      value TEXT
    );

    CREATE TABLE IF NOT EXISTS managers (
      id INTEGER PRIMARY KEY,
      name TEXT,
      player_name TEXT,
      points_total INTEGER DEFAULT 0,
      wins INTEGER DEFAULT 0,
      draws INTEGER DEFAULT 0,
      losses INTEGER DEFAULT 0,
      points_for INTEGER DEFAULT 0,
      points_against INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS gameweek_scores (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      manager_id INTEGER,
      event INTEGER,
      points INTEGER,
      bench_points INTEGER DEFAULT 0,
      total_points INTEGER,
      UNIQUE(manager_id, event)
    );

    CREATE TABLE IF NOT EXISTS h2h_matches (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      event INTEGER,
      manager_1_id INTEGER,
      manager_2_id INTEGER,
      manager_1_points INTEGER,
      manager_2_points INTEGER,
      winner_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS players (
      id INTEGER PRIMARY KEY,
      web_name TEXT,
      first_name TEXT,
      second_name TEXT,
      team INTEGER,
      position INTEGER,
      total_points INTEGER,
      goals_scored INTEGER,
      assists INTEGER,
      clean_sheets INTEGER,
      minutes INTEGER,
      form REAL,
      ict_index REAL,
      expected_goals REAL,
      expected_assists REAL,
      draft_rank INTEGER,
      status TEXT
    );

    CREATE TABLE IF NOT EXISTS team_picks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      manager_id INTEGER,
      event INTEGER,
      player_id INTEGER,
      position INTEGER,
      is_captain INTEGER DEFAULT 0,
      multiplier INTEGER DEFAULT 1,
      UNIQUE(manager_id, event, player_id)
    );

    CREATE TABLE IF NOT EXISTS draft_picks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      round INTEGER,
      pick INTEGER,
      manager_id INTEGER,
      player_id INTEGER,
      was_auto INTEGER DEFAULT 0
    );

    CREATE TABLE IF NOT EXISTS transactions (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      manager_id INTEGER,
      event INTEGER,
      player_in_id INTEGER,
      player_out_id INTEGER,
      kind TEXT,
      result TEXT,
      added TEXT
    );
  `);
}

// --- Metadata helpers ---

function getMeta(key) {
  const row = getDb().prepare('SELECT value FROM metadata WHERE key = ?').get(key);
  return row ? row.value : null;
}

function setMeta(key, value) {
  getDb().prepare('INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)').run(key, String(value));
}

// --- Upsert helpers ---

function upsertManager(m) {
  getDb().prepare(`
    INSERT INTO managers (id, name, player_name, points_total, wins, draws, losses, points_for, points_against)
    VALUES (@id, @name, @player_name, @points_total, @wins, @draws, @losses, @points_for, @points_against)
    ON CONFLICT(id) DO UPDATE SET
      name=@name, player_name=@player_name, points_total=@points_total,
      wins=@wins, draws=@draws, losses=@losses,
      points_for=@points_for, points_against=@points_against
  `).run(m);
}

function upsertGameweekScore(s) {
  getDb().prepare(`
    INSERT INTO gameweek_scores (manager_id, event, points, bench_points, total_points)
    VALUES (@manager_id, @event, @points, @bench_points, @total_points)
    ON CONFLICT(manager_id, event) DO UPDATE SET
      points=@points, bench_points=@bench_points, total_points=@total_points
  `).run(s);
}

function insertH2hMatch(m) {
  getDb().prepare(`
    INSERT INTO h2h_matches (event, manager_1_id, manager_2_id, manager_1_points, manager_2_points, winner_id)
    VALUES (@event, @manager_1_id, @manager_2_id, @manager_1_points, @manager_2_points, @winner_id)
  `).run(m);
}

function clearH2hMatches() {
  getDb().prepare('DELETE FROM h2h_matches').run();
}

function upsertPlayer(p) {
  getDb().prepare(`
    INSERT INTO players (id, web_name, first_name, second_name, team, position,
      total_points, goals_scored, assists, clean_sheets, minutes, form,
      ict_index, expected_goals, expected_assists, draft_rank, status)
    VALUES (@id, @web_name, @first_name, @second_name, @team, @position,
      @total_points, @goals_scored, @assists, @clean_sheets, @minutes, @form,
      @ict_index, @expected_goals, @expected_assists, @draft_rank, @status)
    ON CONFLICT(id) DO UPDATE SET
      web_name=@web_name, first_name=@first_name, second_name=@second_name,
      team=@team, position=@position, total_points=@total_points,
      goals_scored=@goals_scored, assists=@assists, clean_sheets=@clean_sheets,
      minutes=@minutes, form=@form, ict_index=@ict_index,
      expected_goals=@expected_goals, expected_assists=@expected_assists,
      draft_rank=@draft_rank, status=@status
  `).run(p);
}

function upsertTeamPick(tp) {
  getDb().prepare(`
    INSERT INTO team_picks (manager_id, event, player_id, position, is_captain, multiplier)
    VALUES (@manager_id, @event, @player_id, @position, @is_captain, @multiplier)
    ON CONFLICT(manager_id, event, player_id) DO UPDATE SET
      position=@position, is_captain=@is_captain, multiplier=@multiplier
  `).run(tp);
}

function clearDraftPicks() {
  getDb().prepare('DELETE FROM draft_picks').run();
}

function insertDraftPick(dp) {
  getDb().prepare(`
    INSERT INTO draft_picks (round, pick, manager_id, player_id, was_auto)
    VALUES (@round, @pick, @manager_id, @player_id, @was_auto)
  `).run(dp);
}

function clearTransactions() {
  getDb().prepare('DELETE FROM transactions').run();
}

function insertTransaction(t) {
  getDb().prepare(`
    INSERT INTO transactions (manager_id, event, player_in_id, player_out_id, kind, result, added)
    VALUES (@manager_id, @event, @player_in_id, @player_out_id, @kind, @result, @added)
  `).run(t);
}

// --- Query helpers ---

function getAllManagers() {
  return getDb().prepare('SELECT * FROM managers ORDER BY points_total DESC').all();
}

function getGameweekScores() {
  return getDb().prepare('SELECT * FROM gameweek_scores ORDER BY event, manager_id').all();
}

function getH2hMatches() {
  return getDb().prepare('SELECT * FROM h2h_matches ORDER BY event').all();
}

function getH2hBetween(id1, id2) {
  return getDb().prepare(`
    SELECT * FROM h2h_matches
    WHERE (manager_1_id = ? AND manager_2_id = ?)
       OR (manager_1_id = ? AND manager_2_id = ?)
    ORDER BY event
  `).all(id1, id2, id2, id1);
}

function getAllPlayers() {
  return getDb().prepare('SELECT * FROM players ORDER BY total_points DESC').all();
}

function getTeamPicks(managerId, event) {
  if (managerId && event) {
    return getDb().prepare('SELECT * FROM team_picks WHERE manager_id = ? AND event = ?').all(managerId, event);
  }
  if (managerId) {
    return getDb().prepare('SELECT * FROM team_picks WHERE manager_id = ? ORDER BY event, position').all(managerId);
  }
  return getDb().prepare('SELECT * FROM team_picks ORDER BY manager_id, event, position').all();
}

function getLatestTeamPicks() {
  // Get picks from the most recent gameweek for each manager
  return getDb().prepare(`
    SELECT tp.* FROM team_picks tp
    INNER JOIN (
      SELECT manager_id, MAX(event) as max_event
      FROM team_picks
      GROUP BY manager_id
    ) latest ON tp.manager_id = latest.manager_id AND tp.event = latest.max_event
    ORDER BY tp.manager_id, tp.position
  `).all();
}

function getDraftPicks() {
  return getDb().prepare('SELECT * FROM draft_picks ORDER BY round, pick').all();
}

function getTransactions() {
  return getDb().prepare('SELECT * FROM transactions ORDER BY added DESC').all();
}

function getManagerCount() {
  const row = getDb().prepare('SELECT COUNT(*) as cnt FROM managers').get();
  return row.cnt;
}

function getLastSyncedEvent() {
  const val = getMeta('last_synced_event');
  return val ? parseInt(val, 10) : 0;
}

function setLastSyncedEvent(event) {
  setMeta('last_synced_event', event);
}

module.exports = {
  getDb,
  getMeta,
  setMeta,
  upsertManager,
  upsertGameweekScore,
  insertH2hMatch,
  clearH2hMatches,
  upsertPlayer,
  upsertTeamPick,
  clearDraftPicks,
  insertDraftPick,
  clearTransactions,
  insertTransaction,
  getAllManagers,
  getGameweekScores,
  getH2hMatches,
  getH2hBetween,
  getAllPlayers,
  getTeamPicks,
  getLatestTeamPicks,
  getDraftPicks,
  getTransactions,
  getManagerCount,
  getLastSyncedEvent,
  setLastSyncedEvent,
};
