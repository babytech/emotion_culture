const { installSystemInfoCompatShim } = require("./utils/system-info-compat");
installSystemInfoCompatShim();

const config = require("./config/index");
const { initCloud } = require("./services/cloud");
const { getStudyQuizPaper } = require("./services/api");
const { detectRuntimeEnv } = require("./utils/runtime");
const {
  isValidQuizPaperPayload,
  shouldPrefetchQuizPaper,
  writeQuizPaperCache,
} = require("./utils/study-quiz-paper-cache");

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
    this.prewarmStudyQuizPaper();
  },

  prewarmStudyQuizPaper() {
    if (this._quizPaperWarmupInFlight) return;
    if (!shouldPrefetchQuizPaper()) return;

    this._quizPaperWarmupInFlight = true;
    getStudyQuizPaper("english")
      .then((paper) => {
        if (!isValidQuizPaperPayload(paper)) return;
        writeQuizPaperCache(paper);
      })
      .catch(() => {
        // ignore warmup errors
      })
      .finally(() => {
        this._quizPaperWarmupInFlight = false;
      });
  },
});
