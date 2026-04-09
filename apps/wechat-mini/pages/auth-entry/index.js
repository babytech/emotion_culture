const { bindWechatPhone } = require("../../services/api");
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

function mapPhoneBindFailure(detail) {
  const errMsg = typeof detail.errMsg === "string" ? detail.errMsg : "";
  const errno = Number(detail.errno);
  const raw = `${errMsg} ${Number.isFinite(errno) ? errno : ""}`.toLowerCase();

  if (!errMsg) {
    return "微信号码授权失败，请重试";
  }
  if (raw.includes("user deny") || raw.includes("user cancel")) {
    return "你已取消号码授权";
  }
  if (raw.includes("privacy")) {
    return "请先点击同意，再绑定号码";
  }
  if (raw.includes("no permission") || raw.includes("jsapi has no permission")) {
    return "当前小程序暂不具备手机号能力，请检查 AppID 主体和接口权限";
  }
  if (raw.includes("login") || raw.includes("wxlogin")) {
    return "微信登录态未就绪，请稍后重试";
  }
  return "微信号码授权失败，请重试";
}

function buildPageState(rawState, extras = {}) {
  const state = rawState || getAuthGateState();
  const loginState = state.login_state || AUTH_LOGIN_STATES.LOGGED_OUT;
  const maskedPhone = state.masked_phone || "";
  const isLoggedIn = loginState === AUTH_LOGIN_STATES.LOGGED_IN;
  const agreed = state.agreed === true;
  const privacyAuthorized = state.privacy_authorized === true;

  let statusTitle = "未登录";
  let statusSubtitle = "登录后可查看绑定数据";
  let statusChip = "未登录";
  let phoneHint = agreed ? "点击按钮完成绑定" : "请先点击同意";

  if (loginState === AUTH_LOGIN_STATES.PHONE_PENDING) {
    statusTitle = "待绑定号码";
    statusSubtitle = "再完成一步即可进入首页";
    statusChip = "待完成";
  }

  if (isLoggedIn) {
    statusTitle = "已登录";
    statusSubtitle = "微信身份已完成绑定";
    statusChip = "已登录";
    phoneHint = maskedPhone || "微信号码已绑定";
  }

  return {
    loginState,
    agreed,
    privacyAuthorized,
    isLoggedIn,
    statusTitle,
    statusSubtitle,
    statusChip,
    phoneHint,
    maskedPhone,
    privacyContractName: extras.privacyContractName || "",
  };
}

Page({
  data: {
    isBindingPhone: false,
    isAuthorizingPrivacy: false,
    privacyContractName: "",
    loginState: AUTH_LOGIN_STATES.LOGGED_OUT,
    agreed: false,
    privacyAuthorized: false,
    isLoggedIn: false,
    statusTitle: "未登录",
    statusSubtitle: "登录后可查看绑定数据",
    statusChip: "未登录",
    phoneHint: "请先点击同意",
    maskedPhone: "",
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
    let nextState = state;

    if (!state.agreed && privacySetting.needAuthorization === false) {
      nextState = markAuthGateAgreementAccepted({
        identityType: "wechat_phone_pending",
        privacyAuthorized: true,
      });
    }

    this.setData(buildPageState(nextState, { privacyContractName: privacySetting.privacyContractName || "" }));
  },

  warmupWechatLogin() {
    ensureWechatLogin().catch(() => {});
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
        identityType: "wechat_phone_pending",
        privacyAuthorized: true,
      });
      this.setData(buildPageState(nextState, { privacyContractName: this.data.privacyContractName }));
      this.warmupWechatLogin();
      wx.showToast({
        title: "请继续绑定号码",
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

  async handleGetPhoneNumber(event) {
    if (this.data.isBindingPhone) return;
    if (!this.data.agreed) {
      wx.showToast({
        title: "请先点击同意",
        icon: "none",
      });
      return;
    }

    const detail = (event && event.detail) || {};
    const errMsg = typeof detail.errMsg === "string" ? detail.errMsg : "";
    const code = typeof detail.code === "string" ? detail.code.trim() : "";

    if (errMsg && !errMsg.endsWith(":ok")) {
      wx.showToast({
        title: mapPhoneBindFailure(detail),
        icon: "none",
      });
      return;
    }

    if (!code) {
      wx.showToast({
        title: "微信号码授权失败，请重试",
        icon: "none",
      });
      return;
    }

    this.setData({ isBindingPhone: true });
    try {
      const response = await bindWechatPhone({ code });
      const nextState = markAuthGateCompleted({
        identityType: response.identity_type || "wechat_phone_bound",
        openidPresent: response.openid_present === true,
        unionidPresent: response.unionid_present === true,
        maskedPhone: response.masked_phone_number || "",
        phoneBound: response.phone_bound !== false,
        privacyAuthorized: true,
      });
      this.setData(buildPageState(nextState, { privacyContractName: this.data.privacyContractName }));
      wx.showToast({
        title: "已登录",
        icon: "success",
      });
      setTimeout(() => {
        this.finishEntry();
      }, 320);
    } catch (err) {
      wx.showToast({
        title: (err && err.message) || "绑定失败，请重试",
        icon: "none",
      });
    } finally {
      this.setData({ isBindingPhone: false });
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
