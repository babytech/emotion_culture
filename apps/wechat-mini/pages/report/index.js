const { deleteRetentionWeeklyReport, getRetentionWeeklyReport } = require("../../services/api");

function toDate(input) {
  const raw = (input || "").trim();
  if (!raw) return new Date();
  const parsed = new Date(raw);
  if (!Number.isNaN(parsed.getTime())) return parsed;
  return new Date();
}

function toYmd(dateObj) {
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  const dd = String(dateObj.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function toDisplayDate(value) {
  const dateObj = toDate(value);
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  const dd = String(dateObj.getDate()).padStart(2, "0");
  return `${mm}-${dd}`;
}

function mondayOf(dateObj) {
  const clone = new Date(dateObj.getFullYear(), dateObj.getMonth(), dateObj.getDate());
  const day = clone.getDay();
  const shift = day === 0 ? -6 : 1 - day;
  clone.setDate(clone.getDate() + shift);
  return clone;
}

function buildDigestItem(item) {
  const emotion = (item && item.primary_emotion) || {};
  const triggerTags = Array.isArray(item && item.trigger_tags) ? item.trigger_tags : [];
  const hasCheckin = !!(item && item.has_checkin);
  const suggestionSummary = (item && item.suggestion_summary) || "";
  const emotionLabel = (emotion && (emotion.label || emotion.code)) || "";
  return {
    date: (item && item.date) || "",
    displayDate: toDisplayDate((item && item.date) || ""),
    hasCheckin,
    statusText: hasCheckin ? "已打卡" : "未打卡",
    statusClass: hasCheckin ? "ok" : "miss",
    emotionLabel,
    emotionDisplay: emotionLabel || "未识别",
    triggerTags,
    triggerTagsText: triggerTags.join("、"),
    hasTriggerTags: triggerTags.length > 0,
    suggestionSummary,
    hasSuggestionSummary: !!suggestionSummary,
  };
}

function buildDominantEmotionItem(item) {
  const code = ((item && item.code) || "").trim();
  const label = ((item && item.label) || "").trim();
  return {
    code,
    label,
    displayLabel: label || code || "未识别",
    days: Number((item && item.days) || 0),
  };
}

function buildTopTriggerTagItem(item) {
  return {
    tag: ((item && item.tag) || "").trim() || "未标注",
    count: Number((item && item.count) || 0),
  };
}

Page({
  data: {
    isLoading: false,
    cacheActionLoading: false,
    errorMsg: "",
    weekStart: "",
    weekEnd: "",
    weekLabel: "",
    totalCheckinDays: 0,
    checkedToday: false,
    checkedTodayText: "否",
    currentStreak: 0,
    dominantEmotions: [],
    topTriggerTags: [],
    suggestionHighlights: [],
    dailyDigests: [],
    insight: "",
    insightText: "本周暂无可展示洞察。",
    source: "",
  },

  onLoad(options) {
    const requested = (options && options.week_start) || "";
    const start = mondayOf(toDate(requested || toYmd(new Date())));
    const weekStart = toYmd(start);
    this.loadWeeklyReport(weekStart);
  },

  onShow() {
    if (this.data.weekStart) {
      this.loadWeeklyReport(this.data.weekStart);
    }
  },

  async loadWeeklyReport(weekStart) {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });
    try {
      const result = await getRetentionWeeklyReport(weekStart);
      const start = (result && result.week_start) || weekStart || "";
      const end = (result && result.week_end) || "";

      this.setData({
        weekStart: start,
        weekEnd: end,
        weekLabel: start && end ? `${toDisplayDate(start)} ~ ${toDisplayDate(end)}` : "",
        totalCheckinDays: Number(result && result.total_checkin_days) || 0,
        checkedToday: !!(result && result.checked_today),
        checkedTodayText: result && result.checked_today ? "是" : "否",
        currentStreak: Number(result && result.current_streak) || 0,
        dominantEmotions: Array.isArray(result && result.dominant_emotions)
          ? result.dominant_emotions.map(buildDominantEmotionItem)
          : [],
        topTriggerTags: Array.isArray(result && result.top_trigger_tags)
          ? result.top_trigger_tags.map(buildTopTriggerTagItem)
          : [],
        suggestionHighlights: Array.isArray(result && result.suggestion_highlights)
          ? result.suggestion_highlights
          : [],
        dailyDigests: Array.isArray(result && result.daily_digests)
          ? result.daily_digests.map(buildDigestItem)
          : [],
        insight: (result && result.insight) || "",
        insightText: (result && result.insight) || "本周暂无可展示洞察。",
        source: (result && result.source) || "",
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "加载周报失败，请稍后重试。",
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  shiftWeek(days) {
    const start = mondayOf(toDate(this.data.weekStart || toYmd(new Date())));
    start.setDate(start.getDate() + days);
    const next = toYmd(start);
    this.loadWeeklyReport(next);
  },

  goPrevWeek() {
    this.shiftWeek(-7);
  },

  goNextWeek() {
    this.shiftWeek(7);
  },

  retryLoad() {
    if (this.data.isLoading || this.data.cacheActionLoading) return;
    const weekStart = (this.data.weekStart || "").trim() || toYmd(mondayOf(new Date()));
    this.loadWeeklyReport(weekStart);
  },

  async handleDeleteCurrentWeekSnapshot() {
    const weekStart = (this.data.weekStart || "").trim();
    if (!weekStart) {
      return;
    }

    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: "删除周报快照",
        content: "将删除当前周报缓存，稍后会重新生成，是否继续？",
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
    if (!confirmed) {
      return;
    }

    this.setData({ cacheActionLoading: true, errorMsg: "" });
    try {
      const result = await deleteRetentionWeeklyReport(weekStart);
      const deleted = Number(result && result.deleted_count) || 0;
      wx.showToast({
        title: deleted > 0 ? "已删除周报缓存" : "当前周无缓存",
        icon: "none",
      });
      await this.loadWeeklyReport(weekStart);
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "删除周报缓存失败，请稍后重试。",
      });
      wx.showToast({
        title: "删除失败",
        icon: "none",
      });
    } finally {
      this.setData({ cacheActionLoading: false });
    }
  },

  goCalendar() {
    wx.navigateTo({ url: "/pages/calendar/index" });
  },
});
