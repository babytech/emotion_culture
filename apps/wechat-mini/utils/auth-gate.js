const { ANALYZE_TAB, FAVORITES_TAB, HOME_TAB, JOURNEY_TAB, PROFILE_TAB } = require("./tabbar");

const AUTH_GATE_STORAGE_KEY = "ec_phase5_auth_gate_v1";
const AUTH_GATE_VERSION = 3;
const AUTH_ENTRY_PATH = "/pages/auth-entry/index";
const ALLOWED_TARGETS = [HOME_TAB, JOURNEY_TAB, ANALYZE_TAB, FAVORITES_TAB, PROFILE_TAB];
const AUTH_LOGIN_STATES = {
  LOGGED_OUT: "logged_out",
  PHONE_PENDING: "phone_pending",
  LOGGED_IN: "logged_in",
};

function buildDefaultAuthGateState() {
  return {
    version: AUTH_GATE_VERSION,
    completed: false,
    agreed: false,
    phone_bound: false,
    login_state: AUTH_LOGIN_STATES.LOGGED_OUT,
    agreement_at: "",
    phone_bound_at: "",
    confirmed_at: "",
    identity_type: "",
    openid_present: false,
    unionid_present: false,
    masked_phone: "",
  };
}

function normalizeBoolean(value) {
  return value === true;
}

function normalizeString(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeAuthGateState(value) {
  const fallback = buildDefaultAuthGateState();
  if (!value || typeof value !== "object") {
    return fallback;
  }
  if (Number(value.version) !== AUTH_GATE_VERSION) {
    return fallback;
  }

  const agreed = normalizeBoolean(value.agreed);
  const phoneBound = normalizeBoolean(value.phone_bound);
  const completed = normalizeBoolean(value.completed);

  let loginState = AUTH_LOGIN_STATES.LOGGED_OUT;
  if (completed) {
    loginState = AUTH_LOGIN_STATES.LOGGED_IN;
  } else if (agreed) {
    loginState = AUTH_LOGIN_STATES.PHONE_PENDING;
  }

  return {
    version: AUTH_GATE_VERSION,
    completed,
    agreed,
    phone_bound: completed ? true : phoneBound,
    login_state: loginState,
    agreement_at: normalizeString(value.agreement_at),
    phone_bound_at: normalizeString(value.phone_bound_at),
    confirmed_at: normalizeString(value.confirmed_at),
    identity_type: normalizeString(value.identity_type),
    openid_present: normalizeBoolean(value.openid_present),
    unionid_present: normalizeBoolean(value.unionid_present),
    masked_phone: normalizeString(value.masked_phone),
  };
}

function saveAuthGateState(nextState) {
  const normalized = normalizeAuthGateState(nextState);
  try {
    wx.setStorageSync(AUTH_GATE_STORAGE_KEY, normalized);
  } catch (err) {
    // ignore
  }
  return normalized;
}

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
    return normalizeAuthGateState(value);
  } catch (err) {
    return buildDefaultAuthGateState();
  }
}

function hasCompletedAuthGate() {
  const state = getAuthGateState();
  return state.completed === true;
}

function markAuthGateAgreementAccepted(payload = {}) {
  const current = getAuthGateState();
  const agreementAt = current.agreement_at || new Date().toISOString();
  return saveAuthGateState({
    ...current,
    agreed: true,
    agreement_at: agreementAt,
    identity_type: normalizeString(payload.identityType) || current.identity_type,
    openid_present: payload.openidPresent === true || current.openid_present,
    unionid_present: payload.unionidPresent === true || current.unionid_present,
  });
}

function markAuthGatePhoneBound(payload = {}) {
  const current = getAuthGateState();
  const phoneBoundAt = current.phone_bound_at || new Date().toISOString();
  return saveAuthGateState({
    ...current,
    agreed: true,
    phone_bound: true,
    phone_bound_at: phoneBoundAt,
    masked_phone: normalizeString(payload.maskedPhone) || current.masked_phone,
    identity_type: normalizeString(payload.identityType) || current.identity_type,
    openid_present: payload.openidPresent === true || current.openid_present,
    unionid_present: payload.unionidPresent === true || current.unionid_present,
  });
}

function markAuthGateCompleted(payload = {}) {
  const current = getAuthGateState();
  const now = new Date().toISOString();
  const nextState = {
    ...current,
    completed: true,
    agreed: true,
    phone_bound: payload.phoneBound !== false,
    agreement_at: current.agreement_at || now,
    phone_bound_at: current.phone_bound_at || now,
    confirmed_at: now,
    identity_type: normalizeString(payload.identityType) || current.identity_type,
    openid_present: payload.openidPresent === true || current.openid_present,
    unionid_present: payload.unionidPresent === true || current.unionid_present,
    masked_phone: normalizeString(payload.maskedPhone) || current.masked_phone,
  };
  return saveAuthGateState(nextState);
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
  AUTH_LOGIN_STATES,
  buildDefaultAuthGateState,
  clearAuthGateState,
  ensurePhase5Auth,
  getAuthGateState,
  hasCompletedAuthGate,
  markAuthGateAgreementAccepted,
  markAuthGatePhoneBound,
  markAuthGateCompleted,
  normalizeTargetTab,
  redirectToAuthEntry,
};
