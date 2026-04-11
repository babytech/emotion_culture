const TODAY_HISTORY_FOCUS_KEY = "ec_today_history_focus_v1";

function normalizeReason(reason) {
  return typeof reason === "string" ? reason.trim() : "";
}

function requestTodayHistoryFocus(reason) {
  const payload = {
    reason: normalizeReason(reason) || "unknown",
    requested_at: new Date().toISOString(),
  };
  try {
    wx.setStorageSync(TODAY_HISTORY_FOCUS_KEY, payload);
  } catch (err) {
    // ignore
  }
  return payload;
}

function consumeTodayHistoryFocusRequest() {
  try {
    const raw = wx.getStorageSync(TODAY_HISTORY_FOCUS_KEY);
    wx.removeStorageSync(TODAY_HISTORY_FOCUS_KEY);
    if (!raw || typeof raw !== "object") {
      return null;
    }
    return {
      reason: normalizeReason(raw.reason) || "unknown",
      requestedAt: normalizeReason(raw.requested_at),
    };
  } catch (err) {
    return null;
  }
}

module.exports = {
  consumeTodayHistoryFocusRequest,
  requestTodayHistoryFocus,
};
