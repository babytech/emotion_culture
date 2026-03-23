const config = require("../config/index");

function inferExt(path) {
  if (!path) return ".dat";
  const idx = path.lastIndexOf(".");
  if (idx < 0) return ".dat";
  return path.substring(idx);
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

async function uploadTempFile(tempFilePath, category) {
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

  const result = await wx.cloud.uploadFile({
    cloudPath,
    filePath: tempFilePath,
  });

  if (!result || !result.fileID) {
    throw new Error("upload failed: no fileID returned.");
  }

  let tempFileURL = "";
  try {
    const urlResult = await wx.cloud.getTempFileURL({
      fileList: [result.fileID],
      // long enough for immediate analyze/email flow; fileID remains the durable fallback.
      maxAge: 2 * 60 * 60,
    });
    const entry = (urlResult && urlResult.fileList && urlResult.fileList[0]) || {};
    tempFileURL = entry.tempFileURL || "";
  } catch (err) {
    // Keep flow available even if temp URL fetch fails; backend can fallback to fileID.
    console.warn("getTempFileURL failed, fallback to fileID only", err);
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
