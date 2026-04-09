const { markAuthGateCompleted, hasCompletedAuthGate, normalizeTargetTab } = require("../../utils/auth-gate");
const { HOME_TAB } = require("../../utils/tabbar");

Page({
  data: {
    isEntering: false,
    loginHint: "点击按钮后，将直接使用当前微信账号进入小程序。",
  },

  onLoad(options) {
    this.targetTab = normalizeTargetTab((options && options.target) || HOME_TAB);
  },

  onShow() {
    if (hasCompletedAuthGate()) {
      this.finishEntry();
    }
  },

  async handleAgreeAndEnter() {
    if (this.data.isEntering) return;
    this.setData({ isEntering: true });
    try {
      if (typeof wx.login === "function") {
        try {
          await new Promise((resolve, reject) => {
            wx.login({
              success(res) {
                if (res && res.code) {
                  resolve(res.code);
                  return;
                }
                reject(new Error("微信登录态获取失败"));
              },
              fail(err) {
                reject(err || new Error("微信登录态获取失败"));
              },
            });
          });
        } catch (err) {
          // Mini program production identity still relies on later cloud container requests.
          // Do not block entry on transient wx.login failure.
        }
      }

      markAuthGateCompleted({
        identityType: "wechat_direct_entry",
        openidPresent: true,
        unionidPresent: false,
      });
      this.finishEntry();
    } finally {
      this.setData({ isEntering: false });
    }
  },

  finishEntry() {
    const targetTab = this.targetTab || HOME_TAB;
    wx.switchTab({
      url: targetTab,
      fail: () => {
        wx.reLaunch({ url: targetTab });
      },
    });
  },
});
