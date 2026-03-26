const { deleteHistoryItem, getHistoryDetail } = require("../../services/api");

function toDisplayTime(value) {
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

Page({
  data: {
    historyId: "",
    isLoading: false,
    errorMsg: "",
    summary: null,
    resultCard: null,
    internalFields: null,
    displayTime: "",
  },

  onLoad(options) {
    const historyId = (options && options.id && decodeURIComponent(options.id)) || "";
    this.setData({ historyId });
  },

  onShow() {
    if (this.data.historyId) {
      this.loadDetail();
    } else {
      this.setData({ errorMsg: "缺少历史记录 ID。" });
    }
  },

  async loadDetail() {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });

    try {
      const detail = await getHistoryDetail(this.data.historyId);
      const summary = (detail && detail.summary) || null;
      this.setData({
        summary,
        resultCard: (detail && detail.result_card) || null,
        internalFields: (detail && detail.internal_fields) || null,
        displayTime: summary ? toDisplayTime(summary.analyzed_at) : "",
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "加载历史详情失败。",
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  async handleDelete() {
    const historyId = this.data.historyId;
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
      wx.showToast({
        title: "已删除",
        icon: "none",
      });
      wx.navigateBack({
        delta: 1,
        fail() {
          wx.reLaunch({ url: "/pages/history/index" });
        },
      });
    } catch (err) {
      wx.showToast({
        title: (err && err.message) || "删除失败",
        icon: "none",
      });
    }
  },

  backToHistory() {
    wx.navigateBack({
      delta: 1,
      fail() {
        wx.reLaunch({ url: "/pages/history/index" });
      },
    });
  },

  backToAnalyze() {
    wx.reLaunch({ url: "/pages/index/index" });
  },
});
