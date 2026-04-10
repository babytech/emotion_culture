const { getBootstrap } = require("../../services/api");
const {
  AUTH_LOGIN_STATES,
  getAuthGateState,
  hasCompletedAuthGate,
  markAuthGateAgreementAccepted,
  markAuthGateCompleted,
} = require("../../utils/auth-gate");
const { HOME_TAB } = require("../../utils/tabbar");

function ensureWechatLogin() {
  if (typeof wx.login !== "function") {
    return Promise.resolve("");
  }
  return new Promise((resolve) => {
    wx.login({
      success(res) {
        resolve((res && res.code) || "");
      },
      fail() {
        resolve("");
      },
    });
  });
}

function getPrivacySetting() {
  if (typeof wx.getPrivacySetting !== "function") {
    return Promise.resolve({
      supported: false,
      needAuthorization: false,
      privacyContractName: "",
    });
  }
  return new Promise((resolve) => {
    wx.getPrivacySetting({
      success(res) {
        resolve({
          supported: true,
          needAuthorization: !!(res && res.needAuthorization),
          privacyContractName: (res && res.privacyContractName) || "",
        });
      },
      fail() {
        resolve({
          supported: true,
          needAuthorization: true,
          privacyContractName: "",
        });
      },
    });
  });
}

function requirePrivacyAuthorization() {
  if (typeof wx.requirePrivacyAuthorize !== "function") {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    wx.requirePrivacyAuthorize({
      success(res) {
        resolve(res);
      },
      fail(err) {
        reject(err || new Error("隐私授权未完成"));
      },
    });
  });
}

function buildBootstrapIdentityPayload(bootstrap) {
  if (!bootstrap || typeof bootstrap !== "object") {
    return null;
  }
  if (bootstrap.user_bound !== true) {
    return null;
  }
  return {
    identityType: (bootstrap && bootstrap.identity_type) || "wechat_direct_entry",
    openidPresent: !!(bootstrap && bootstrap.openid_present),
    unionidPresent: !!(bootstrap && bootstrap.unionid_present),
    privacyAuthorized: true,
  };
}

function buildPageState(rawState, extras = {}) {
  const state = rawState || getAuthGateState();
  const loginState = state.login_state || AUTH_LOGIN_STATES.LOGGED_OUT;
  const isLoggedIn = loginState === AUTH_LOGIN_STATES.LOGGED_IN;
  const agreed = state.agreed === true;
  const privacyAuthorized = state.privacy_authorized === true;

  let statusTitle = "未登录";
  let statusSubtitle = "同意后使用当前微信身份进入首页";
  let statusChip = "未登录";
  let enterHint = agreed ? "点击按钮后，将使用当前微信身份进入首页" : "请先点击同意";

  if (loginState === AUTH_LOGIN_STATES.READY) {
    statusTitle = "待进入";
    statusSubtitle = "当前微信身份已可进入首页";
    statusChip = "待完成";
    enterHint = "历史记录、会员、积分将绑定当前微信身份";
  }

  if (isLoggedIn) {
    statusTitle = "已登录";
    statusSubtitle = "当前微信身份已完成绑定";
    statusChip = "已登录";
    enterHint = "历史记录、会员、积分已绑定当前微信身份";
  }

  return {
    loginState,
    agreed,
    privacyAuthorized,
    isLoggedIn,
    statusTitle,
    statusSubtitle,
    statusChip,
    enterHint,
    privacyContractName: extras.privacyContractName || "",
  };
}

Page({
  data: {
    isAuthorizingPrivacy: false,
    isEnteringWechat: false,
    privacyContractName: "",
    loginState: AUTH_LOGIN_STATES.LOGGED_OUT,
    agreed: false,
    privacyAuthorized: false,
    isLoggedIn: false,
    statusTitle: "未登录",
    statusSubtitle: "同意后使用当前微信身份进入首页",
    statusChip: "未登录",
    enterHint: "请先点击同意",
    profileRows: [
      { key: "history", icon: "评", title: "我的记录", hint: "登录后查看" },
      { key: "favorites", icon: "藏", title: "我的收藏", hint: "登录后查看" },
      { key: "member", icon: "会", title: "会员权益", hint: "登录后查看" },
      { key: "protocol", icon: "约", title: "协议与条款", hint: "查看" },
    ],
  },

  onLoad() {
    this.targetTab = HOME_TAB;
    this.warmupWechatLogin();
  },

  async onShow() {
    if (hasCompletedAuthGate()) {
      this.finishEntry();
      return;
    }
    await this.refreshPageState();
    this.warmupWechatLogin();
  },

  async refreshPageState() {
    const state = getAuthGateState();
    const privacySetting = await getPrivacySetting();
    this.setData(buildPageState(state, { privacyContractName: privacySetting.privacyContractName || "" }));
  },

  warmupWechatLogin() {
    ensureWechatLogin().catch(() => {});
  },

  syncBootstrapIdentity() {
    getBootstrap()
      .then((bootstrap) => {
        const payload = buildBootstrapIdentityPayload(bootstrap);
        if (!payload) return;
        markAuthGateCompleted(payload);
      })
      .catch(() => {});
  },

  openPrivacyContract() {
    if (typeof wx.openPrivacyContract !== "function") {
      wx.showToast({
        title: "当前微信版本不支持查看",
        icon: "none",
      });
      return;
    }

    wx.openPrivacyContract({
      fail: () => {
        wx.showToast({
          title: "暂时无法打开隐私协议",
          icon: "none",
        });
      },
    });
  },

  async handleAgreeTap() {
    if (this.data.isAuthorizingPrivacy || this.data.agreed) return;
    this.setData({ isAuthorizingPrivacy: true });
    try {
      await requirePrivacyAuthorization();
      const nextState = markAuthGateAgreementAccepted({
        identityType: "wechat_identity_ready",
        privacyAuthorized: true,
      });
      this.setData(buildPageState(nextState, { privacyContractName: this.data.privacyContractName }));
      this.warmupWechatLogin();
      wx.showToast({
        title: "请使用当前微信身份进入",
        icon: "none",
      });
    } catch (err) {
      wx.showToast({
        title: "你还没有完成隐私授权",
        icon: "none",
      });
    } finally {
      this.setData({ isAuthorizingPrivacy: false });
    }
  },

  async handleEnterWithWechat() {
    if (this.data.isEnteringWechat) return;
    if (!this.data.agreed) {
      wx.showToast({
        title: "请先点击同意",
        icon: "none",
      });
      return;
    }

    this.setData({ isEnteringWechat: true });
    try {
      await ensureWechatLogin();
      const nextState = markAuthGateCompleted({
        identityType: "wechat_direct_entry",
        privacyAuthorized: true,
      });
      this.setData(buildPageState(nextState, { privacyContractName: this.data.privacyContractName }));
      this.syncBootstrapIdentity();
      wx.showToast({
        title: "已进入首页",
        icon: "success",
      });
      setTimeout(() => {
        this.finishEntry();
      }, 260);
    } catch (err) {
      wx.showToast({
        title: (err && err.message) || "微信身份初始化失败，请稍后重试",
        icon: "none",
      });
    } finally {
      this.setData({ isEnteringWechat: false });
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
