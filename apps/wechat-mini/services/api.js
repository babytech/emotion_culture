const config = require("../config/index");

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

function isInvalidHostError(errMsg) {
  return typeof errMsg === "string" && errMsg.includes("INVALID_HOST");
}

function callContainerOnce(path, method, data, env) {
  return new Promise((resolve, reject) => {
    if (!wx.cloud || !wx.cloud.callContainer) {
      reject(new Error("wx.cloud.callContainer is unavailable"));
      return;
    }

    wx.cloud.callContainer({
      config: { env },
      path,
      method,
      data,
      header: {
        "X-WX-SERVICE": config.containerService,
        "content-type": "application/json",
      },
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
  return callViaContainer("/api/analyze", "POST", payload);
}

function sendEmail(payload) {
  return callViaContainer("/api/send-email", "POST", payload, {
    retryOnInvalidHost: true,
    fallbackPaths: ["/api/send_email"],
  });
}

module.exports = {
  analyze,
  normalizeAssetUrl,
  sendEmail,
};
