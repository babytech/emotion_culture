const { clearHistory, getSettings, updateSettings } = require("../../services/api");
const { ensurePhase5Auth } = require("../../utils/auth-gate");
const { ANALYZE_TAB, FAVORITES_TAB, PROFILE_TAB, setTabBarSelected } = require("../../utils/tabbar");

const FEEDBACK_EMAIL = "microbabytech@gmail.com";
const QUICK_ACTIONS = [
  { key: "history", title: "历史记录", subtitle: "查看全部摘要与详情", badge: "轨迹", tone: "history" },
  { key: "favorites", title: "我的收藏", subtitle: "回看收藏过的内容", badge: "收藏", tone: "favorites" },
  { key: "analyze", title: "继续分析", subtitle: "回到分析工作台", badge: "分析", tone: "analyze" },
  { key: "settings", title: "更多设置", subtitle: "进入设置页查看扩展项", badge: "设置", tone: "settings" },
];
const PRIVACY_CARDS = [
  {
    key: "save",
    title: "保存什么",
    body: "仅保存分析结果摘要、打卡状态与周报缓存，方便后续回看。",
    badge: "保存",
  },
  {
    key: "raw",
    title: "不长期保存什么",
    body: "原始自拍、图片和录音不会长期保存，只用于本次分析或短期失败恢复。",
    badge: "媒体",
  },
  {
    key: "delete",
    title: "你可以怎么删除",
    body: "你可以随时删除单条历史、清空全部历史、取消收藏或清除周报缓存。",
    badge: "删除",
  },
  {
    key: "scope",
    title: "使用边界",
    body: "本项目仅作情绪文化陪伴，不作医疗诊断或治疗建议。",
    badge: "说明",
  },
];

function formatUpdatedAtText(value) {
  const raw = (value || "").trim();
  return raw ? `最近更新：${raw}` : "最近更新：尚未同步";
}

function formatUpdatedAtValue(value) {
  const raw = (value || "").trim();
  return raw || "尚未同步";
}

Page({
  data: {
    isLoading: false,
    isSaving: false,
    saveHistory: true,
    retentionDays: 180,
    updatedAtValue: "尚未同步",
    updatedAtText: "最近更新：尚未同步",
    errorMsg: "",
    quickActions: QUICK_ACTIONS,
    privacyCards: PRIVACY_CARDS,
    feedbackEmail: FEEDBACK_EMAIL,
  },

  onShow() {
    if (ensurePhase5Auth(PROFILE_TAB)) return;
    setTabBarSelected(this, PROFILE_TAB);
    this.loadSettings();
  },

  async loadSettings() {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });

    try {
      const settings = await getSettings();
      this.setData({
        saveHistory: settings.save_history !== false,
        retentionDays: Number(settings.history_retention_days) || 180,
        updatedAtValue: formatUpdatedAtValue(settings.updated_at || ""),
        updatedAtText: formatUpdatedAtText(settings.updated_at || ""),
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "加载设置失败，请稍后重试。",
      });
    } finally {
      this.setData({ isLoading: false });
    }
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
        updatedAtValue: formatUpdatedAtValue(settings.updated_at || ""),
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
    const key = (event && event.currentTarget && event.currentTarget.dataset.key) || "";
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
    if (key === "settings") {
      this.goSettingsDetail();
    }
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
