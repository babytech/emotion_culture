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
    return "请先完成隐私授权，再点击绑定号码";
  }
  if (raw.includes("no permission") || raw.includes("jsapi has no permission")) {
    return "当前小程序暂不具备手机号能力，请检查 AppID 主体和接口权限";
  }
  if (raw.includes("login") || raw.includes("wxlogin")) {
    return "微信登录态未就绪，请稍后重试";
  }
  return "微信号码授权失败，请重试";
}

function buildPageState(rawState) {
  const state = rawState || getAuthGateState();
  const loginState = state.login_state || AUTH_LOGIN_STATES.LOGGED_OUT;
  const maskedPhone = state.masked_phone || "";
  const isLoggedIn = loginState === AUTH_LOGIN_STATES.LOGGED_IN;
  const agreed = state.agreed === true;

  let title = "未登录";
  let subtitle = "先同意，再绑定微信号码";
  let chip = "未登录";
  let phoneHint = agreed ? "点击按钮完成绑定" : "先完成上一步";

  if (loginState === AUTH_LOGIN_STATES.PHONE_PENDING) {
    title = "待绑定号码";
    subtitle = "再完成一步即可进入首页";
    chip = "待完成";
  }

  if (isLoggedIn) {
    title = "已登录";
    subtitle = "微信身份已完成绑定";
    chip = "已登录";
    phoneHint = maskedPhone || "微信号码已绑定";
  }

  return {
    loginState,
    agreed,
    isLoggedIn,
    statusTitle: title,
    statusSubtitle: subtitle,
    statusChip: chip,
    phoneHint,
    maskedPhone,
  };
}

Page({
  data: {
    agreementVisible: false,
    isBindingPhone: false,
    supportsPrivacyAuthorization: false,
    loginState: AUTH_LOGIN_STATES.LOGGED_OUT,
    agreed: false,
    isLoggedIn: false,
    statusTitle: "未登录",
    statusSubtitle: "先同意，再绑定微信号码",
    statusChip: "未登录",
    phoneHint: "先完成上一步",
    maskedPhone: "",
  },

  onLoad() {
    this.targetTab = HOME_TAB;
    this.setData({
      supportsPrivacyAuthorization: typeof wx.getPrivacySetting === "function",
    });
    this.warmupWechatLogin();
  },

  onShow() {
    if (hasCompletedAuthGate()) {
      this.finishEntry();
      return;
    }
    this.syncPageState();
    this.warmupWechatLogin();
  },

  warmupWechatLogin() {
    ensureWechatLogin().catch(() => {});
  },

  syncPageState(state) {
    this.setData(buildPageState(state));
  },

  openAgreementSheet() {
    if (this.data.isBindingPhone || this.data.isLoggedIn) return;
    this.setData({ agreementVisible: true });
  },

  closeAgreementSheet() {
    this.setData({ agreementVisible: false });
  },

  handleAgreementReject() {
    this.closeAgreementSheet();
    wx.showToast({
      title: "需同意后才能继续",
      icon: "none",
    });
  },

  handleAgreementAccept() {
    const nextState = markAuthGateAgreementAccepted({
      identityType: "wechat_phone_pending",
    });
    this.setData({ agreementVisible: false });
    this.syncPageState(nextState);
    this.warmupWechatLogin();
    wx.showToast({
      title: "请继续绑定号码",
      icon: "none",
    });
  },

  handleAgreementAcceptFallback() {
    this.handleAgreementAccept();
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

  noop() {},

  async handleGetPhoneNumber(event) {
    if (this.data.isBindingPhone || !this.data.agreed) return;

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
      });
      this.syncPageState(nextState);
      wx.showToast({
        title: "已登录",
        icon: "success",
      });
      setTimeout(() => {
        this.finishEntry();
      }, 360);
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
