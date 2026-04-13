const { clearHistory, getCheckinStatus, getSettings, updateSettings } = require("../../services/api");
const { ensurePhase5Auth } = require("../../utils/auth-gate");
const { ANALYZE_TAB, FAVORITES_TAB, PROFILE_TAB, setTabBarSelected } = require("../../utils/tabbar");

const FEEDBACK_EMAIL = "babytech@126.com";
const QUICK_ACTIONS = [
  { key: "history", title: "我的记录", icon: "记" },
  { key: "favorites", title: "我的收藏", icon: "藏" },
  { key: "analyze", title: "继续分析", icon: "析" },
  { key: "checkin", title: "每日签到", icon: "签" },
  { key: "settings", title: "设置", icon: "设" },
];

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

Page({
  data: {
    isLoading: false,
    isSaving: false,
    saveHistory: true,
    retentionDays: 180,
    updatedAtText: "最近更新：尚未同步",
    errorMsg: "",
    quickActions: QUICK_ACTIONS,
    privacyExpanded: false,
    feedbackEmail: FEEDBACK_EMAIL,
    memberName: "微信用户",
    memberLevel: "普通会员",
    checkin: normalizeCheckin({}),
  },

  onShow() {
    if (ensurePhase5Auth(PROFILE_TAB)) return;
    setTabBarSelected(this, PROFILE_TAB);
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

  handleQuickAction(event) {
    const key = safeText(event && event.currentTarget && event.currentTarget.dataset.key);
    if (!key) return;
    if (key === "history") {
      this.goHistory();
      return;
    }
    if (key === "favorites") {
      this.goFavorites();
      return;
    }
    if (key === "analyze") {
      this.goAnalyze();
      return;
    }
    if (key === "checkin") {
      this.openCheckinPage();
      return;
    }
    if (key === "settings") {
      this.goSettingsDetail();
    }
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
    wx.switchTab({ url: FAVORITES_TAB });
  },

  goAnalyze() {
    wx.switchTab({ url: ANALYZE_TAB });
  },

  goSettingsDetail() {
    wx.navigateTo({ url: "/pages/settings/index" });
  },
});
