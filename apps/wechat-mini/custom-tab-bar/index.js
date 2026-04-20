const { HOME_TAB, JOURNEY_TAB, PROFILE_TAB } = require("../utils/tabbar");

const TAB_ITEMS = [
  { pagePath: HOME_TAB, text: "首页" },
  { pagePath: JOURNEY_TAB, text: "记录" },
  { pagePath: PROFILE_TAB, text: "我的" },
];

Component({
  data: {
    selected: HOME_TAB,
    items: TAB_ITEMS,
    keyboardHeight: 0,
    isCompact: false,
  },

  lifetimes: {
    attached() {
      try {
        const windowInfo = typeof wx.getWindowInfo === "function" ? wx.getWindowInfo() : {};
        const deviceInfo = typeof wx.getDeviceInfo === "function" ? wx.getDeviceInfo() : {};
        const windowWidth =
          Number(windowInfo && windowInfo.windowWidth) ||
          Number(windowInfo && windowInfo.screenWidth) ||
          Number(deviceInfo && deviceInfo.screenWidth) ||
          0;
        this.setData({
          isCompact: windowWidth > 0 && windowWidth <= 360,
        });
      } catch (err) {
        // ignore
      }
      if (wx.onKeyboardHeightChange) {
        this._keyboardHandler = (res) => {
          this.setData({
            keyboardHeight: Math.max(0, Number(res && res.height) || 0),
          });
        };
        wx.onKeyboardHeightChange(this._keyboardHandler);
      }
    },

    detached() {
      if (this._keyboardHandler && wx.offKeyboardHeightChange) {
        wx.offKeyboardHeightChange(this._keyboardHandler);
      }
    },
  },

  methods: {
    handleTabTap(event) {
      const url = (event && event.currentTarget && event.currentTarget.dataset.url) || "";
      if (!url || url === this.data.selected) return;
      wx.switchTab({ url });
    },
  },
});
