const PATCH_FLAG = "__ec_system_info_compat_installed__";

function safeCall(fn) {
  try {
    if (typeof fn === "function") {
      return fn() || {};
    }
  } catch (err) {
    // ignore
  }
  return {};
}

function buildSystemInfoSnapshot() {
  const deviceInfo = safeCall(wx.getDeviceInfo);
  const windowInfo = safeCall(wx.getWindowInfo);
  const appBaseInfo = safeCall(wx.getAppBaseInfo);
  const systemSetting = safeCall(wx.getSystemSetting);
  const appAuthorizeSetting = safeCall(wx.getAppAuthorizeSetting);

  return {
    errMsg: "getSystemInfo:ok",
    ...deviceInfo,
    ...windowInfo,
    ...appBaseInfo,
    ...systemSetting,
    ...appAuthorizeSetting,
  };
}

function normalizeCallbackOptions(options) {
  if (options && typeof options === "object") {
    return options;
  }
  return {};
}

function invokeSafely(fn, payload) {
  if (typeof fn !== "function") return;
  try {
    fn(payload);
  } catch (err) {
    // ignore callback errors
  }
}

function installSystemInfoCompatShim() {
  if (typeof wx === "undefined" || !wx) return false;
  if (wx[PATCH_FLAG]) return true;

  const canBuildSnapshot =
    typeof wx.getDeviceInfo === "function" &&
    typeof wx.getWindowInfo === "function" &&
    typeof wx.getAppBaseInfo === "function";
  if (!canBuildSnapshot) return false;

  wx.getSystemInfo = function getSystemInfoCompat(options) {
    const normalized = normalizeCallbackOptions(options);
    try {
      const snapshot = buildSystemInfoSnapshot();
      invokeSafely(normalized.success, snapshot);
      invokeSafely(normalized.complete, snapshot);
    } catch (err) {
      const error = {
        errMsg: (err && err.message) || "getSystemInfo:fail",
      };
      invokeSafely(normalized.fail, error);
      invokeSafely(normalized.complete, error);
    }
  };

  wx.getSystemInfoSync = function getSystemInfoSyncCompat() {
    return buildSystemInfoSnapshot();
  };

  wx[PATCH_FLAG] = true;
  return true;
}

module.exports = {
  installSystemInfoCompatShim,
};
