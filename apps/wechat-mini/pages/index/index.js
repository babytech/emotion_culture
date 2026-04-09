const { HOME_TAB } = require("../../utils/tabbar");
const { ensurePhase5Auth } = require("../../utils/auth-gate");

Page({
  data: {
    redirectFailed: false,
  },

  onShow() {
    if (ensurePhase5Auth(HOME_TAB)) return;
    wx.switchTab({
      url: HOME_TAB,
      fail: () => {
        this.setData({ redirectFailed: true });
      },
    });
  },

  openHome() {
    wx.switchTab({ url: HOME_TAB });
  },
});
