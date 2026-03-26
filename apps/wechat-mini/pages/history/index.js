const { clearHistory, deleteHistoryItem, listHistory } = require("../../services/api");

const INPUT_MODE_LABELS = {
  text: "文字",
  voice: "语音",
  selfie: "自拍",
  pc_camera: "摄像头",
};

function formatDateTime(value) {
  const raw = (value || "").trim();
  if (!raw) return "未知时间";

  const normalized = raw.endsWith("Z") ? raw.replace("Z", "+00:00") : raw;
  const date = new Date(normalized);
  if (!Number.isNaN(date.getTime())) {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, "0");
    const dd = String(date.getDate()).padStart(2, "0");
    const hh = String(date.getHours()).padStart(2, "0");
    const mi = String(date.getMinutes()).padStart(2, "0");
    return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
  }

  return raw.replace("T", " ").replace("Z", "");
}

function toModeText(modes) {
  if (!Array.isArray(modes) || modes.length === 0) {
    return "未知输入";
  }

  const labels = [];
  modes.forEach((mode) => {
    const label = INPUT_MODE_LABELS[mode] || mode;
    if (!labels.includes(label)) labels.push(label);
  });
  return labels.join(" / ");
}

function toSecondaryText(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return "暂无";
  }
  const labels = [];
  items.forEach((item) => {
    const label = (item && item.label) || (item && item.code) || "";
    if (label && !labels.includes(label)) {
      labels.push(label);
    }
  });
  return labels.length ? labels.join("、") : "暂无";
}

Page({
  data: {
    items: [],
    total: 0,
    isLoading: false,
    isClearing: false,
    errorMsg: "",
  },

  onShow() {
    this.loadHistory();
  },

  async loadHistory() {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });

    try {
      const result = await listHistory({ limit: 50, offset: 0 });
      const rawItems = (result && result.items) || [];

      const items = rawItems.map((item) => ({
        historyId: item.history_id || "",
        requestId: item.request_id || "",
        analyzedAt: item.analyzed_at || "",
        displayTime: formatDateTime(item.analyzed_at),
        primaryEmotionLabel:
          (item.primary_emotion && (item.primary_emotion.label || item.primary_emotion.code)) || "未识别",
        secondaryEmotionText: toSecondaryText(item.secondary_emotions),
        emotionOverviewSummary: item.emotion_overview_summary || "暂无概述",
        inputModesText: toModeText(item.input_modes),
        mailSent: !!item.mail_sent,
      }));

      this.setData({
        items,
        total: Number(result && result.total) || items.length,
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "加载历史失败，请稍后重试。",
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  openDetail(event) {
    const historyId = (event && event.currentTarget && event.currentTarget.dataset.id) || "";
    if (!historyId) return;
    wx.navigateTo({
      url: `/pages/history/detail?id=${encodeURIComponent(historyId)}`,
    });
  },

  async handleDeleteItem(event) {
    const historyId = (event && event.currentTarget && event.currentTarget.dataset.id) || "";
    if (!historyId) return;

    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: "删除记录",
        content: "确认删除这条历史记录吗？",
        confirmText: "删除",
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
      await deleteHistoryItem(historyId);
      wx.showToast({ title: "已删除", icon: "none" });
      await this.loadHistory();
    } catch (err) {
      wx.showToast({
        title: (err && err.message) || "删除失败",
        icon: "none",
      });
    }
  },

  async handleClearAll() {
    if (this.data.isClearing) return;

    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: "清空历史",
        content: "将删除全部历史记录，是否继续？",
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

    this.setData({ isClearing: true });
    try {
      const result = await clearHistory();
      const deletedCount = Number(result && result.deleted_count) || 0;
      wx.showToast({
        title: deletedCount > 0 ? `已清空 ${deletedCount} 条` : "历史记录已为空",
        icon: "none",
      });
      await this.loadHistory();
    } catch (err) {
      wx.showToast({
        title: (err && err.message) || "清空失败",
        icon: "none",
      });
    } finally {
      this.setData({ isClearing: false });
    }
  },

  goSettings() {
    wx.navigateTo({ url: "/pages/settings/index" });
  },
});
