const { ANALYZE_TAB, FAVORITES_TAB, HOME_TAB, JOURNEY_TAB, PROFILE_TAB } = require("./tabbar");

const AUTH_GATE_STORAGE_KEY = "ec_phase5_auth_gate_v1";
const AUTH_GATE_VERSION = 1;
const AUTH_ENTRY_PATH = "/pages/auth-entry/index";
const ALLOWED_TARGETS = [HOME_TAB, JOURNEY_TAB, ANALYZE_TAB, FAVORITES_TAB, PROFILE_TAB];

function normalizeTargetTab(targetTab) {
  const raw = typeof targetTab === "string" ? targetTab.trim() : "";
  if (!raw) return HOME_TAB;
  return ALLOWED_TARGETS.includes(raw) ? raw : HOME_TAB;
}

function buildAuthEntryUrl(targetTab) {
  const normalizedTarget = normalizeTargetTab(targetTab);
  return `${AUTH_ENTRY_PATH}?target=${encodeURIComponent(normalizedTarget)}`;
}

function getAuthGateState() {
  try {
    const value = wx.getStorageSync(AUTH_GATE_STORAGE_KEY);
    if (!value || typeof value !== "object") return null;
    if (Number(value.version) !== AUTH_GATE_VERSION) return null;
    return value;
  } catch (err) {
    return null;
  }
}

function hasCompletedAuthGate() {
  const state = getAuthGateState();
  return !!(state && state.completed === true);
}

function markAuthGateCompleted(payload = {}) {
  const nextState = {
    version: AUTH_GATE_VERSION,
    completed: true,
    confirmed_at: new Date().toISOString(),
    identity_type: typeof payload.identityType === "string" ? payload.identityType : "",
    openid_present: payload.openidPresent === true,
    unionid_present: payload.unionidPresent === true,
  };
  try {
    wx.setStorageSync(AUTH_GATE_STORAGE_KEY, nextState);
  } catch (err) {
    // ignore
  }
  return nextState;
}

function clearAuthGateState() {
  try {
    wx.removeStorageSync(AUTH_GATE_STORAGE_KEY);
  } catch (err) {
    // ignore
  }
}

function redirectToAuthEntry(targetTab) {
  const url = buildAuthEntryUrl(targetTab);
  wx.reLaunch({ url });
}

function ensurePhase5Auth(targetTab) {
  if (hasCompletedAuthGate()) return false;
  redirectToAuthEntry(targetTab);
  return true;
}

module.exports = {
  AUTH_ENTRY_PATH,
  clearAuthGateState,
  ensurePhase5Auth,
  getAuthGateState,
  hasCompletedAuthGate,
  markAuthGateCompleted,
  normalizeTargetTab,
  redirectToAuthEntry,
};
