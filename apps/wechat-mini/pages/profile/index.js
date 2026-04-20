const { clearHistory, getCheckinStatus, getSettings, updateSettings } = require("../../services/api");
const { ensurePhase5Auth } = require("../../utils/auth-gate");
const { FAVORITES_TAB, PROFILE_TAB, setTabBarSelected } = require("../../utils/tabbar");

const FEEDBACK_EMAIL = "babytech@126.com";
const WECHAT_PROFILE_STORAGE_KEY = "ec_wechat_profile_v1";

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function formatUpdatedAtText(value) {
  const raw = safeText(value);
  return raw ? `最近更新：${raw}` : "最近更新：尚未同步";
}

function normalizeCheckin(raw) {
  const source = raw && typeof raw === "object" ? raw : {};
  return {
    signedToday: !!source.signed_today,
    currentStreak: Math.max(0, Number(source.current_streak) || 0),
    pointsBalance: Math.max(0, Number(source.points_balance) || 0),
    message: safeText(source.message) || "每日签到可获得积分",
  };
}

function buildAvatarText(name) {
  const normalized = safeText(name);
  if (!normalized) return "微";
  return normalized.slice(0, 1);
}

function normalizeWechatProfile(raw) {
  if (!raw || typeof raw !== "object") return null;
  const nickName = safeText(raw.nickName || raw.nickname || raw.name);
  const avatarUrl = safeText(raw.avatarUrl || raw.avatar || raw.avatar_url);
  if (!nickName && !avatarUrl) return null;
  return {
    nickName: nickName || "微信用户",
    avatarUrl,
  };
}

Page({
  data: {
    isLoading: false,
    isSaving: false,
    isSyncingProfile: false,
    saveHistory: true,
    retentionDays: 180,
    updatedAtText: "最近更新：尚未同步",
    errorMsg: "",
    privacyExpanded: false,
    feedbackEmail: FEEDBACK_EMAIL,
    memberName: "微信用户",
    memberLevel: "微信身份已绑定",
    memberAvatarUrl: "",
    memberAvatarText: "微",
    checkin: normalizeCheckin({}),
  },

  onShow() {
    if (ensurePhase5Auth(PROFILE_TAB)) return;
    setTabBarSelected(this, PROFILE_TAB);
    this.loadStoredWechatProfile();
    this.trySyncWechatProfileSilently();
    this.loadAllData();
  },

  async loadAllData() {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });
    const [settingsRes, checkinRes] = await Promise.allSettled([getSettings(), getCheckinStatus()]);

    const nextData = {};
    if (settingsRes.status === "fulfilled") {
      const settings = settingsRes.value || {};
      nextData.saveHistory = settings.save_history !== false;
      nextData.retentionDays = Number(settings.history_retention_days) || 180;
      nextData.updatedAtText = formatUpdatedAtText(settings.updated_at || "");
    } else {
      nextData.errorMsg = (settingsRes.reason && settingsRes.reason.message) || "加载设置失败，请稍后重试。";
    }

    if (checkinRes.status === "fulfilled") {
      nextData.checkin = normalizeCheckin(checkinRes.value);
    }

    this.setData({
      ...nextData,
      isLoading: false,
    });
  },

  async handleSaveHistoryChange(event) {
    const nextValue = !!(event && event.detail && event.detail.value);
    const previous = this.data.saveHistory;

    this.setData({
      saveHistory: nextValue,
      isSaving: true,
      errorMsg: "",
    });

    try {
      const settings = await updateSettings({ save_history: nextValue });
      this.setData({
        saveHistory: settings.save_history !== false,
        retentionDays: Number(settings.history_retention_days) || this.data.retentionDays,
        updatedAtText: formatUpdatedAtText(settings.updated_at || ""),
      });
      wx.showToast({
        title: nextValue ? "已开启历史保存" : "已关闭历史保存",
        icon: "none",
      });
    } catch (err) {
      this.setData({
        saveHistory: previous,
        errorMsg: (err && err.message) || "更新设置失败，请稍后重试。",
      });
      wx.showToast({
        title: "设置更新失败",
        icon: "none",
      });
    } finally {
      this.setData({ isSaving: false });
    }
  },

  async handleClearHistory() {
    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: "清空历史记录",
        content: "将删除你保存的全部历史摘要，是否继续？",
        confirmText: "清空",
        cancelText: "取消",
        success(res) {
          resolve(!!(res && res.confirm));
        },
        fail() {
          resolve(false);
        },
      });
    });
    if (!confirmed) return;

    try {
      const result = await clearHistory();
      const deletedCount = Number(result && result.deleted_count) || 0;
      wx.showToast({
        title: deletedCount > 0 ? `已清空 ${deletedCount} 条` : "历史记录已为空",
        icon: "none",
      });
    } catch (err) {
      wx.showToast({
        title: (err && err.message) || "清空失败",
        icon: "none",
      });
    }
  },

  copyFeedbackEmail() {
    wx.setClipboardData({
      data: FEEDBACK_EMAIL,
      success: () => {
        wx.showToast({
          title: "反馈邮箱已复制",
          icon: "none",
        });
      },
      fail: () => {
        wx.showToast({
          title: "复制失败，请手动记录邮箱",
          icon: "none",
        });
      },
    });
  },

  togglePrivacyExpanded() {
    this.setData({
      privacyExpanded: !this.data.privacyExpanded,
    });
  },

  openCheckinPage() {
    wx.navigateTo({ url: "/pages/checkin/index" });
  },

  goHistory() {
    wx.navigateTo({ url: "/pages/history/index" });
  },

  goFavorites() {
    wx.navigateTo({ url: FAVORITES_TAB });
  },

  goSettingsDetail() {
    wx.navigateTo({ url: "/pages/settings/index" });
  },

  loadStoredWechatProfile() {
    let stored = null;
    try {
      stored = wx.getStorageSync(WECHAT_PROFILE_STORAGE_KEY);
    } catch (err) {
      stored = null;
    }
    const profile = normalizeWechatProfile(stored);
    if (!profile) return;
    this.applyWechatProfile(profile);
  },

  saveWechatProfile(profile) {
    try {
      wx.setStorageSync(WECHAT_PROFILE_STORAGE_KEY, {
        nickName: profile.nickName,
        avatarUrl: profile.avatarUrl,
        updatedAt: new Date().toISOString(),
      });
    } catch (err) {
      // ignore
    }
  },

  applyWechatProfile(profile) {
    const normalized = normalizeWechatProfile(profile);
    if (!normalized) return;
    this.setData({
      memberName: normalized.nickName || "微信用户",
      memberAvatarUrl: normalized.avatarUrl || "",
      memberAvatarText: buildAvatarText(normalized.nickName || "微信用户"),
    });
  },

  trySyncWechatProfileSilently() {
    if (typeof wx.getSetting !== "function" || typeof wx.getUserInfo !== "function") return;
    wx.getSetting({
      success: (settingRes) => {
        const authSetting = (settingRes && settingRes.authSetting) || {};
        if (!authSetting["scope.userInfo"]) return;
        wx.getUserInfo({
          success: (userInfoRes) => {
            const userInfo = normalizeWechatProfile(userInfoRes && userInfoRes.userInfo);
            if (!userInfo) return;
            this.applyWechatProfile(userInfo);
            this.saveWechatProfile(userInfo);
          },
        });
      },
    });
  },

  syncWechatProfile() {
    if (this.data.isSyncingProfile) return;
    if (typeof wx.getUserProfile !== "function") {
      wx.showToast({
        title: "当前微信版本不支持同步昵称头像",
        icon: "none",
      });
      return;
    }
    this.setData({ isSyncingProfile: true });
    wx.getUserProfile({
      desc: "用于在“我的”页展示你的微信昵称和头像",
      success: (res) => {
        const userInfo = normalizeWechatProfile(res && res.userInfo);
        if (!userInfo) {
          wx.showToast({
            title: "未获取到昵称头像",
            icon: "none",
          });
          return;
        }
        this.applyWechatProfile(userInfo);
        this.saveWechatProfile(userInfo);
        wx.showToast({
          title: "昵称头像已同步",
          icon: "none",
        });
      },
      fail: (err) => {
        wx.showToast({
          title: (err && err.errMsg) ? "你还没有授权昵称头像" : "同步失败，请稍后重试",
          icon: "none",
        });
      },
      complete: () => {
        this.setData({ isSyncingProfile: false });
      },
    });
  },
});
