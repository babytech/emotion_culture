function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function getDeviceInfoSafe() {
  try {
    if (typeof wx !== "undefined" && typeof wx.getDeviceInfo === "function") {
      return wx.getDeviceInfo() || {};
    }
  } catch (err) {
    // ignore
  }
  return {};
}

function getWindowInfoSafe() {
  try {
    if (typeof wx !== "undefined" && typeof wx.getWindowInfo === "function") {
      return wx.getWindowInfo() || {};
    }
  } catch (err) {
    // ignore
  }
  return {};
}

function getNavigatorUASafe() {
  try {
    if (typeof navigator !== "undefined" && typeof navigator.userAgent === "string") {
      return navigator.userAgent;
    }
  } catch (err) {
    // ignore
  }
  return "";
}

function detectRuntimeEnv() {
  const deviceInfo = getDeviceInfoSafe();
  const windowInfo = getWindowInfoSafe();
  const platform = safeText(deviceInfo.platform).toLowerCase();
  const system = safeText(deviceInfo.system);
  const systemLower = system.toLowerCase();
  const userAgent = getNavigatorUASafe();

  const isDevtools = platform === "devtools";
  // Official HarmonyOS adaptation:
  // 1) device: wx.getDeviceInfo().platform === "ohos"
  // 2) devtools simulation: platform is "devtools" and system can be "HarmonyOS"
  const isOhosPlatform = platform === "ohos";
  const isHarmonyDevtools = isDevtools && system === "HarmonyOS";
  const isHarmonySystem = systemLower.includes("harmonyos") || systemLower.includes("openharmony");
  const isOpenHarmonyUA = /openharmony/i.test(userAgent);
  const isHarmonyOS = isOhosPlatform || isHarmonyDevtools || isHarmonySystem || isOpenHarmonyUA;

  const clientPlatform = isHarmonyOS ? "mp-weixin-ohos" : "mp-weixin";

  return {
    platform,
    system,
    userAgent,
    isDevtools,
    isHarmonyOS,
    clientPlatform,
    statusBarHeight: Number(windowInfo.statusBarHeight) || 0,
  };
}

module.exports = {
  detectRuntimeEnv,
};
