const { clearHistory, getSettings, updateSettings } = require("../../services/api");

function formatUpdatedAtText(value) {
  const raw = (value || "").trim();
  return raw ? `最近更新：${raw}` : "";
}

Page({
  data: {
    isLoading: false,
    isSaving: false,
    saveHistory: true,
    retentionDays: 180,
    updatedAt: "",
    updatedAtText: "",
    errorMsg: "",
  },

  onShow() {
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
        updatedAt: settings.updated_at || "",
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
        updatedAt: settings.updated_at || "",
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
    const target = "babytech@126.com";
    wx.setClipboardData({
      data: target,
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

  goHistory() {
    wx.navigateTo({ url: "/pages/history/index" });
  },

  goFavorites() {
    wx.navigateTo({ url: "/pages/favorites/index" });
  },
});
