const { clearHistory, deleteHistoryItem, getHistoryTimeline } = require("../../services/api");
const { getQuizCourseLabel } = require("../../utils/study-quiz-course");

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function formatDateTime(value) {
  const raw = safeText(value);
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

function tabLabelByType(type) {
  if (type === "emotion") return "情绪分析";
  if (type === "quiz") return "伴学小测";
  return "全部";
}

function mapTimelineItem(item) {
  const itemType = safeText(item && item.item_type) || "emotion";
  const isQuiz = itemType === "quiz";
  const quizGrade = safeText(item && item.quiz_grade);
  return {
    timelineId: safeText(item && item.timeline_id),
    itemType,
    displayTime: formatDateTime(item && item.occurred_at),
    title: safeText(item && item.title) || "未命名记录",
    subtitle: safeText(item && item.subtitle),
    emotionHistoryId: safeText(item && item.emotion_history_id),
    quizRecordId: safeText(item && item.quiz_record_id),
    quizScore: Math.max(0, Number(item && item.quiz_score) || 0),
    quizGrade,
    quizGradeLabel: quizGrade || "-",
    quizCourse: safeText(item && item.quiz_course),
    quizCourseLabel: getQuizCourseLabel(item && item.quiz_course),
    typeLabel: isQuiz ? "伴学小测" : "情绪分析",
    typeBadgeClass: isQuiz ? "history-badge-quiz" : "history-badge-emotion",
    actionLabel: isQuiz ? "查看成绩" : "查看详情",
  };
}

Page({
  data: {
    items: [],
    total: 0,
    timelineType: "all",
    activeFilterLabel: "全部",
    filterTabs: [
      { key: "all", label: "全部" },
      { key: "emotion", label: "情绪分析" },
      { key: "quiz", label: "伴学小测" },
    ],
    isLoading: false,
    isClearing: false,
    errorMsg: "",
  },

  onShow() {
    this.setData({
      activeFilterLabel: tabLabelByType(this.data.timelineType),
    });
    this.loadTimeline();
  },

  onPullDownRefresh() {
    this.loadTimeline().finally(() => {
      wx.stopPullDownRefresh();
    });
  },

  async loadTimeline() {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });

    try {
      const result = await getHistoryTimeline({
        type: this.data.timelineType,
        limit: 80,
        offset: 0,
      });
      const rawItems = (result && result.items) || [];
      const items = rawItems.map(mapTimelineItem);

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

  handleFilterChange(event) {
    const nextType = ((event && event.currentTarget && event.currentTarget.dataset.type) || "").trim();
    if (!nextType || nextType === this.data.timelineType) return;
    const nextLabel = tabLabelByType(nextType);
    this.setData({
      timelineType: nextType,
      activeFilterLabel: nextLabel,
    }, () => {
      this.loadTimeline();
    });
  },

  openDetail(event) {
    const itemType = (event && event.currentTarget && event.currentTarget.dataset.type) || "";
    const emotionHistoryId = (event && event.currentTarget && event.currentTarget.dataset.emotionId) || "";
    const quizRecordId = (event && event.currentTarget && event.currentTarget.dataset.quizId) || "";

    if (itemType === "quiz" && quizRecordId) {
      wx.navigateTo({
        url: `/pages/study-quiz-result/index?quiz_record_id=${encodeURIComponent(quizRecordId)}&from=history`,
      });
      return;
    }
    if (!emotionHistoryId) return;
    wx.navigateTo({
      url: `/pages/history/detail?id=${encodeURIComponent(emotionHistoryId)}`,
    });
  },

  async handleDeleteItem(event) {
    const itemType = (event && event.currentTarget && event.currentTarget.dataset.type) || "";
    const historyId = (event && event.currentTarget && event.currentTarget.dataset.emotionId) || "";
    if (itemType !== "emotion") {
      wx.showToast({
        title: "小测记录暂不支持单条删除",
        icon: "none",
      });
      return;
    }
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
      await this.loadTimeline();
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
        title: "清空情绪历史",
        content: "将删除全部情绪分析历史记录，是否继续？",
        confirmText: "清空情绪历史",
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
        title: deletedCount > 0 ? `已清空 ${deletedCount} 条情绪记录` : "情绪历史已为空",
        icon: "none",
      });
      await this.loadTimeline();
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
