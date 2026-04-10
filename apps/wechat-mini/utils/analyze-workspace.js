const ANALYZE_WORKSPACE_RESET_KEY = "ec_analyze_workspace_reset_v1";

function normalizeReason(reason) {
  return typeof reason === "string" ? reason.trim() : "";
}

function requestAnalyzeWorkspaceReset(reason) {
  const payload = {
    reason: normalizeReason(reason) || "unknown",
    requested_at: new Date().toISOString(),
  };
  try {
    wx.setStorageSync(ANALYZE_WORKSPACE_RESET_KEY, payload);
  } catch (err) {
    // ignore
  }
  return payload;
}

function consumeAnalyzeWorkspaceResetRequest() {
  try {
    const raw = wx.getStorageSync(ANALYZE_WORKSPACE_RESET_KEY);
    wx.removeStorageSync(ANALYZE_WORKSPACE_RESET_KEY);
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
  consumeAnalyzeWorkspaceResetRequest,
  requestAnalyzeWorkspaceReset,
};
