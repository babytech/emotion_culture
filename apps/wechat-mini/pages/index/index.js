const { ANALYZE_TAB } = require("../../utils/tabbar");
const { ensurePhase5Auth } = require("../../utils/auth-gate");

Page({
  data: {
    redirectFailed: false,
  },

  onShow() {
    if (ensurePhase5Auth(ANALYZE_TAB)) return;
    wx.switchTab({
      url: ANALYZE_TAB,
      fail: () => {
        this.setData({ redirectFailed: true });
      },
    });
  },

  openAnalyze() {
    wx.switchTab({ url: ANALYZE_TAB });
  },
});
