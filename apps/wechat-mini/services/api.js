const config = require("../config/index");
const USER_ID_STORAGE_KEY = "ec_user_id";

function normalizeAssetUrl(rawUrl) {
  if (!rawUrl) return "";
  if (rawUrl.startsWith("http://") || rawUrl.startsWith("https://")) {
    return rawUrl;
  }

  const base = config.apiBaseUrl || "";
  if (!base) return rawUrl;

  const prefix = base.endsWith("/") ? base.slice(0, -1) : base;
  const path = rawUrl.startsWith("/") ? rawUrl : `/${rawUrl}`;
  return `${prefix}${path}`;
}

function buildLocalUserId() {
  const stamp = Date.now().toString(36);
  const rand = Math.random().toString(16).slice(2, 10);
  return `ec_${stamp}_${rand}`;
}

function getOrCreateClientUserId() {
  try {
    const existing = wx.getStorageSync(USER_ID_STORAGE_KEY);
    if (typeof existing === "string" && existing.trim()) {
      return existing.trim();
    }
  } catch (err) {
    // ignore
  }

  const generated = buildLocalUserId();
  try {
    wx.setStorageSync(USER_ID_STORAGE_KEY, generated);
  } catch (err) {
    // ignore
  }
  return generated;
}

function shouldUseClientUserIdFallback() {
  return config.enableClientUserIdFallback === true;
}

function isInvalidHostError(errMsg) {
  return typeof errMsg === "string" && errMsg.includes("INVALID_HOST");
}

function callContainerOnce(path, method, data, env) {
  return new Promise((resolve, reject) => {
    if (!wx.cloud || !wx.cloud.callContainer) {
      reject(new Error("wx.cloud.callContainer is unavailable"));
      return;
    }

    const headers = {
      "X-WX-SERVICE": config.containerService,
      "content-type": "application/json",
    };
    if (shouldUseClientUserIdFallback()) {
      headers["X-EC-USER-ID"] = getOrCreateClientUserId();
    }

    wx.cloud.callContainer({
      config: { env },
      path,
      method,
      data,
      header: headers,
      success(res) {
        const statusCode = typeof res.statusCode === "number" ? res.statusCode : 200;
        if (statusCode >= 200 && statusCode < 300) {
          resolve(res.data);
          return;
        }

        const detail =
          (res.data && (res.data.detail || res.data.message || res.data.code)) ||
          `HTTP ${statusCode}`;
        reject(new Error(detail));
      },
      fail(err) {
        const rawMsg = err && err.errMsg ? err.errMsg : "callContainer request failed";
        reject(new Error(rawMsg));
      },
    });
  });
}

async function callViaContainer(path, method, data, options = {}) {
  const fallbackPaths = Array.isArray(options.fallbackPaths) ? options.fallbackPaths : [];
  const retryOnInvalidHost = Boolean(options.retryOnInvalidHost);

  const preferredEnv = config.containerEnv || config.cloudEnv;
  const envCandidates = [];
  if (preferredEnv) envCandidates.push(preferredEnv);
  if (config.cloudEnv && !envCandidates.includes(config.cloudEnv)) {
    envCandidates.push(config.cloudEnv);
  }

  const pathCandidates = [path, ...fallbackPaths].filter(
    (item, index, arr) => item && arr.indexOf(item) === index
  );

  let lastError = null;
  for (const env of envCandidates) {
    for (const currentPath of pathCandidates) {
      try {
        return await callContainerOnce(currentPath, method, data, env);
      } catch (err) {
        lastError = err;
        if (!retryOnInvalidHost || !isInvalidHostError(err.message)) {
          throw err;
        }
      }
    }
  }

  if (lastError && isInvalidHostError(lastError.message)) {
    throw new Error(
      `云调用目标无效，请检查 containerEnv/containerService（已自动重试）。原始错误: ${lastError.message}`
    );
  }
  throw lastError || new Error("callContainer request failed");
}

function analyze(payload) {
  const data = payload && typeof payload === "object" ? { ...payload } : {};
  const existingClient = data.client && typeof data.client === "object" ? data.client : {};
  data.client = {
    ...existingClient,
    platform: existingClient.platform || "mp-weixin",
    version: existingClient.version || "0.1.0",
  };
  if (!data.client.user_id && shouldUseClientUserIdFallback()) {
    data.client.user_id = getOrCreateClientUserId();
  }
  return callViaContainer("/api/analyze", "POST", data);
}

function sendEmail(payload) {
  return callViaContainer("/api/send-email", "POST", payload, {
    retryOnInvalidHost: true,
    fallbackPaths: ["/api/send_email"],
  });
}

function listHistory(options = {}) {
  const limit = Math.max(1, Math.min(Number(options.limit) || 20, 100));
  const offset = Math.max(0, Number(options.offset) || 0);
  return callViaContainer(`/api/history?limit=${limit}&offset=${offset}`, "GET");
}

function getHistoryDetail(historyId) {
  if (!historyId) {
    return Promise.reject(new Error("historyId is required"));
  }
  return callViaContainer(`/api/history/${encodeURIComponent(historyId)}`, "GET");
}

function deleteHistoryItem(historyId) {
  if (!historyId) {
    return Promise.reject(new Error("historyId is required"));
  }
  return callViaContainer(`/api/history/${encodeURIComponent(historyId)}`, "DELETE");
}

function clearHistory() {
  return callViaContainer("/api/history", "DELETE");
}

function getSettings() {
  return callViaContainer("/api/settings", "GET");
}

function updateSettings(payload) {
  return callViaContainer("/api/settings", "PUT", payload || {});
}

module.exports = {
  analyze,
  clearHistory,
  deleteHistoryItem,
  getHistoryDetail,
  getSettings,
  listHistory,
  normalizeAssetUrl,
  sendEmail,
  updateSettings,
};
