const config = require("./config/index");
const { initCloud } = require("./services/cloud");

App({
  globalData: {
    apiBaseUrl: config.apiBaseUrl,
    latestAnalyzeContext: null,
    latestMediaGenerateState: null,
  },

  onLaunch() {
    initCloud();
  },
});
