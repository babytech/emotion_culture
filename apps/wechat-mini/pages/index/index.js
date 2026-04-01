const { ANALYZE_TAB } = require("../../utils/tabbar");

Page({
  data: {
    redirectFailed: false,
  },

  onShow() {
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
