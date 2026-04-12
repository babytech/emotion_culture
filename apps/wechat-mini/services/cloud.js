const config = require("../config/index");
const DEFAULT_UPLOAD_MAX_RETRIES = 2;
const DEFAULT_TEMP_URL_MAX_RETRIES = 1;
const DEFAULT_RETRY_DELAY_MS = 320;

function inferExt(path) {
  if (!path) return ".dat";
  const idx = path.lastIndexOf(".");
  if (idx < 0) return ".dat";
  return path.substring(idx);
}

function sleep(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function normalizeErrorMessage(err, fallback) {
  return ((err && (err.errMsg || err.message)) || fallback || "").trim();
}

function toNonNegativeInteger(value, fallback) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return fallback;
  return Math.floor(numeric);
}

function isTransientUploadError(message) {
  if (typeof message !== "string") return false;
  const text = message.toLowerCase();
  return (
    text.includes("timeout") ||
    text.includes("timed out") ||
    text.includes("request:fail") ||
    text.includes("network") ||
    text.includes("failed to connect") ||
    text.includes("econnreset") ||
    text.includes("econnaborted") ||
    text.includes("connection reset") ||
    text.includes("request task fail") ||
    text.includes("连接") ||
    text.includes("断开") ||
    text.includes("502") ||
    text.includes("503") ||
    text.includes("504")
  );
}

function uploadFileOnce(cloudPath, filePath) {
  return wx.cloud.uploadFile({
    cloudPath,
    filePath,
  });
}

function getTempFileURLOnce(fileID) {
  return wx.cloud.getTempFileURL({
    fileList: [fileID],
    // long enough for immediate analyze/email flow; fileID remains the durable fallback.
    maxAge: 2 * 60 * 60,
  });
}

function initCloud() {
  if (!wx.cloud) {
    console.warn("wx.cloud is unavailable. Please upgrade base library.");
    return false;
  }

  wx.cloud.init({
    env: config.cloudEnv,
    traceUser: true,
  });
  return true;
}

async function uploadTempFile(tempFilePath, category, options = {}) {
  if (!tempFilePath) {
    throw new Error("tempFilePath is required for upload.");
  }

  if (!wx.cloud) {
    throw new Error("wx.cloud is unavailable.");
  }

  const suffix = inferExt(tempFilePath);
  const stamp = Date.now();
  const rand = Math.random().toString(16).slice(2, 8);
  const cloudPath = `emotion-culture/${category}/${stamp}_${rand}${suffix}`;
  const maxRetries = toNonNegativeInteger(options.maxRetries, DEFAULT_UPLOAD_MAX_RETRIES);
  const tempUrlMaxRetries = toNonNegativeInteger(options.tempUrlMaxRetries, DEFAULT_TEMP_URL_MAX_RETRIES);
  const retryDelayMs = toNonNegativeInteger(options.retryDelayMs, DEFAULT_RETRY_DELAY_MS);
  const onRetry = typeof options.onRetry === "function" ? options.onRetry : null;

  let result = null;
  let lastUploadError = null;
  for (let attempt = 1; attempt <= maxRetries + 1; attempt += 1) {
    try {
      result = await uploadFileOnce(cloudPath, tempFilePath);
      lastUploadError = null;
      break;
    } catch (err) {
      lastUploadError = err;
      const message = normalizeErrorMessage(err, "upload failed");
      const retryable = isTransientUploadError(message);
      const hasNextAttempt = attempt <= maxRetries;
      if (!retryable || !hasNextAttempt) {
        throw new Error(message || "upload failed");
      }
      if (onRetry) {
        onRetry({
          category,
          attempt,
          nextAttempt: attempt + 1,
          maxAttempts: maxRetries + 1,
          delayMs: retryDelayMs * attempt,
          errorMessage: message,
        });
      }
      await sleep(retryDelayMs * attempt);
    }
  }

  if (!result || !result.fileID) {
    const uploadMsg = normalizeErrorMessage(lastUploadError, "upload failed: no fileID returned.");
    throw new Error(uploadMsg);
  }

  let tempFileURL = "";
  for (let attempt = 1; attempt <= tempUrlMaxRetries + 1; attempt += 1) {
    try {
      const urlResult = await getTempFileURLOnce(result.fileID);
      const entry = (urlResult && urlResult.fileList && urlResult.fileList[0]) || {};
      tempFileURL = entry.tempFileURL || "";
      break;
    } catch (err) {
      const message = normalizeErrorMessage(err, "getTempFileURL failed");
      const retryable = isTransientUploadError(message);
      const hasNextAttempt = attempt <= tempUrlMaxRetries;
      if (!retryable || !hasNextAttempt) {
        // Keep flow available even if temp URL fetch fails; backend can fallback to fileID.
        console.warn("getTempFileURL failed, fallback to fileID only", err);
        break;
      }
      await sleep(retryDelayMs * attempt);
    }
  }

  return {
    fileID: result.fileID,
    tempFileURL,
  };
}

module.exports = {
  initCloud,
  uploadTempFile,
};
