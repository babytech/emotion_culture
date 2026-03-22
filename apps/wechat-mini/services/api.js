const config = require("../config/index");

function normalizeAssetUrl(rawUrl) {
  if (!rawUrl) return "";
  if (rawUrl.startsWith("http://") || rawUrl.startsWith("https://")) {
    return rawUrl;
  }

  const prefix = config.apiBaseUrl.endsWith("/")
    ? config.apiBaseUrl.slice(0, -1)
    : config.apiBaseUrl;
  const path = rawUrl.startsWith("/") ? rawUrl : `/${rawUrl}`;
  return `${prefix}${path}`;
}

function request(path, method, data) {
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${config.apiBaseUrl}${path}`,
      method,
      data,
      header: {
        "content-type": "application/json",
      },
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
          return;
        }

        const detail =
          (res.data && (res.data.detail || res.data.message)) ||
          `HTTP ${res.statusCode}`;
        reject(new Error(detail));
      },
      fail(err) {
        reject(new Error(err.errMsg || "network request failed"));
      },
    });
  });
}

function analyze(payload) {
  return request("/api/analyze", "POST", payload);
}

function sendEmail(payload) {
  return request("/api/send-email", "POST", payload);
}

module.exports = {
  analyze,
  normalizeAssetUrl,
  sendEmail,
};
