const fetch = require('node-fetch');

const BASE_URL = 'https://draft.premierleague.com/api';

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let lastRequestTime = 0;
const MIN_INTERVAL = 1000; // 1 second between requests

async function rateLimitedFetch(url) {
  const now = Date.now();
  const elapsed = now - lastRequestTime;
  if (elapsed < MIN_INTERVAL) {
    await delay(MIN_INTERVAL - elapsed);
  }
  lastRequestTime = Date.now();

  const res = await fetch(url, {
    headers: {
      'User-Agent': 'FPL-Draft-Dashboard/1.0',
    },
  });

  if (!res.ok) {
    throw new Error(`FPL API error: ${res.status} ${res.statusText} for ${url}`);
  }

  return res.json();
}

// Get all player data and game settings
async function getBootstrapStatic() {
  return rateLimitedFetch(`${BASE_URL}/bootstrap-static`);
}

// Get current game state (current gameweek, etc.)
async function getGame() {
  return rateLimitedFetch(`${BASE_URL}/game`);
}

// Get league details including standings and H2H matches
async function getLeagueDetails(leagueId) {
  return rateLimitedFetch(`${BASE_URL}/league/${leagueId}/details`);
}

// Get a manager's history (gameweek scores)
async function getEntryHistory(entryId) {
  return rateLimitedFetch(`${BASE_URL}/entry/${entryId}/history`);
}

// Get a manager's picks for a specific gameweek
async function getEntryEvent(entryId, event) {
  return rateLimitedFetch(`${BASE_URL}/entry/${entryId}/event/${event}`);
}

// Get draft picks for a league
async function getDraftChoices(leagueId) {
  return rateLimitedFetch(`${BASE_URL}/draft/${leagueId}/choices`);
}

// Get transactions (waivers, free agents) for a league
async function getTransactions(leagueId) {
  return rateLimitedFetch(`${BASE_URL}/draft/league/${leagueId}/transactions`);
}

// Get element (player) status for a gameweek
async function getEventLive(event) {
  return rateLimitedFetch(`${BASE_URL}/event/${event}/live`);
}

module.exports = {
  getBootstrapStatic,
  getGame,
  getLeagueDetails,
  getEntryHistory,
  getEntryEvent,
  getDraftChoices,
  getTransactions,
  getEventLive,
};
