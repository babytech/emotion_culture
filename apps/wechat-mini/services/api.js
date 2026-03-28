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

function isTimeoutLikeError(errMsg) {
  if (typeof errMsg !== "string") return false;
  const text = errMsg.toLowerCase();
  return (
    text.includes("102002") ||
    text.includes("timeout") ||
    text.includes("timed out") ||
    text.includes("请求超时")
  );
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
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
  const retryOnTimeout = Boolean(options.retryOnTimeout);
  const timeoutRetryCount = Math.max(0, Number(options.timeoutRetryCount) || 0);
  const timeoutRetryDelayMs = Math.max(0, Number(options.timeoutRetryDelayMs) || 300);

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
      let timeoutRetried = 0;
      while (true) {
        try {
          return await callContainerOnce(currentPath, method, data, env);
        } catch (err) {
          lastError = err;
          const message = (err && err.message) || "";
          const canRetryTimeout =
            retryOnTimeout && isTimeoutLikeError(message) && timeoutRetried < timeoutRetryCount;

          if (canRetryTimeout) {
            timeoutRetried += 1;
            await sleep(timeoutRetryDelayMs);
            continue;
          }

          if (retryOnInvalidHost && isInvalidHostError(message)) {
            break;
          }
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
  return callViaContainer("/api/analyze", "POST", data, {
    retryOnTimeout: true,
    timeoutRetryCount: 1,
    timeoutRetryDelayMs: 350,
  });
}

function createAnalyzeTask(payload) {
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
  return callViaContainer("/api/analyze/async", "POST", data, {
    retryOnTimeout: true,
    timeoutRetryCount: 1,
    timeoutRetryDelayMs: 350,
  });
}

function getAnalyzeTask(taskId) {
  const value = (taskId || "").trim();
  if (!value) {
    return Promise.reject(new Error("taskId is required"));
  }
  return callViaContainer(`/api/analyze/async/${encodeURIComponent(value)}`, "GET", undefined, {
    retryOnTimeout: true,
    timeoutRetryCount: 2,
    timeoutRetryDelayMs: 250,
  });
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

function getRetentionCalendar(month) {
  const query = month ? `?month=${encodeURIComponent(month)}` : "";
  return callViaContainer(`/api/retention/calendar${query}`, "GET");
}

function getRetentionWeeklyReport(weekStart) {
  const query = weekStart ? `?week_start=${encodeURIComponent(weekStart)}` : "";
  return callViaContainer(`/api/retention/weekly-report${query}`, "GET");
}

function deleteRetentionWeeklyReport(weekStart) {
  const query = weekStart ? `?week_start=${encodeURIComponent(weekStart)}` : "";
  return callViaContainer(`/api/retention/weekly-report${query}`, "DELETE");
}

function clearRetentionWeeklyReports() {
  return callViaContainer("/api/retention/weekly-reports", "DELETE");
}

function getRetentionWriteSettings() {
  return callViaContainer("/api/retention/write-settings", "GET");
}

function updateRetentionWriteSettings(payload) {
  return callViaContainer("/api/retention/write-settings", "PUT", payload || {});
}

function listFavorites(options = {}) {
  const limit = Math.max(1, Math.min(Number(options.limit) || 20, 100));
  const offset = Math.max(0, Number(options.offset) || 0);
  const type = (options.favoriteType || options.favorite_type || "").trim();
  const parts = [`limit=${limit}`, `offset=${offset}`];
  if (type) {
    parts.push(`favorite_type=${encodeURIComponent(type)}`);
  }
  return callViaContainer(`/api/favorites?${parts.join("&")}`, "GET");
}

function getFavoriteStatus(options = {}) {
  const type = (options.favoriteType || options.favorite_type || "").trim();
  const targetId = (options.targetId || options.target_id || "").trim();
  if (!type || !targetId) {
    return Promise.reject(new Error("favoriteType and targetId are required"));
  }
  return callViaContainer(
    `/api/favorites/status?favorite_type=${encodeURIComponent(type)}&target_id=${encodeURIComponent(targetId)}`,
    "GET"
  );
}

function upsertFavorite(payload) {
  return callViaContainer("/api/favorites", "POST", payload || {});
}

function deleteFavoriteItem(favoriteId) {
  if (!favoriteId) {
    return Promise.reject(new Error("favoriteId is required"));
  }
  return callViaContainer(`/api/favorites/${encodeURIComponent(favoriteId)}`, "DELETE");
}

function clearFavorites(favoriteType) {
  const query = favoriteType ? `?favorite_type=${encodeURIComponent(favoriteType)}` : "";
  return callViaContainer(`/api/favorites${query}`, "DELETE");
}

module.exports = {
  analyze,
  createAnalyzeTask,
  clearHistory,
  clearFavorites,
  deleteHistoryItem,
  deleteFavoriteItem,
  deleteRetentionWeeklyReport,
  clearRetentionWeeklyReports,
  getAnalyzeTask,
  getFavoriteStatus,
  getHistoryDetail,
  getRetentionCalendar,
  getRetentionWeeklyReport,
  getRetentionWriteSettings,
  getSettings,
  listHistory,
  listFavorites,
  normalizeAssetUrl,
  sendEmail,
  upsertFavorite,
  updateRetentionWriteSettings,
  updateSettings,
};
