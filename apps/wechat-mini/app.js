const config = require("./config/index");
const { initCloud } = require("./services/cloud");
const { detectRuntimeEnv } = require("./utils/runtime");

App({
  globalData: {
    apiBaseUrl: config.apiBaseUrl,
    latestAnalyzeContext: null,
    latestMediaGenerateState: null,
    runtimeEnv: {
      isDevtools: false,
      isHarmonyOS: false,
      clientPlatform: "mp-weixin",
      platform: "",
      system: "",
    },
  },

  onLaunch() {
    try {
      this.globalData.runtimeEnv = detectRuntimeEnv();
    } catch (err) {
      // ignore
    }
    initCloud();
  },
});
