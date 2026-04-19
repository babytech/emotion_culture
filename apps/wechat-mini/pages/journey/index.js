const { getDashboardOverviewSnapshot } = require("../../services/dashboard-overview");
const { ensurePhase5Auth } = require("../../utils/auth-gate");
const { consumeTodayHistoryFocusRequest } = require("../../utils/today-history-focus");
const { JOURNEY_TAB, setTabBarSelected } = require("../../utils/tabbar");

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function toDisplayTime(value) {
  const raw = safeText(value);
  if (!raw) return "未知时间";
  const normalized = raw.endsWith("Z") ? raw.replace("Z", "+00:00") : raw;
  const dateObj = new Date(normalized);
  if (Number.isNaN(dateObj.getTime())) {
    return raw.replace("T", " ").replace("Z", "");
  }
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  const dd = String(dateObj.getDate()).padStart(2, "0");
  const hh = String(dateObj.getHours()).padStart(2, "0");
  const mi = String(dateObj.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mi}`;
}

function toRecentItem(item) {
  const primaryEmotion = (item && item.primary_emotion) || {};
  return {
    historyId: safeText(item && item.history_id),
    displayTime: toDisplayTime(item && item.analyzed_at),
    primaryEmotionLabel: safeText(primaryEmotion.label) || safeText(primaryEmotion.code) || "暂未识别",
    summary: safeText(item && item.emotion_overview_summary) || "暂无摘要",
  };
}

function buildTodayHistoryState() {
  return {
    available: false,
    expanded: false,
    monthDay: "",
    eventYear: "",
    headline: "历史上的今天",
    summary: "",
    optionalNote: "",
    statusText: "整理中",
    sourceLabel: "",
    cacheHit: false,
  };
}

function normalizeTodayHistory(raw) {
  const source = raw && typeof raw === "object" ? raw : {};
  const entry = source.entry && typeof source.entry === "object" ? source.entry : {};
  const collapsedDefault = source.collapsed_default !== false;
  return {
    available: !!source.available && !!safeText(entry.headline) && !!safeText(entry.summary),
    expanded: !collapsedDefault,
    monthDay: safeText(source.month_day) || safeText(entry.month_day) || "",
    eventYear: safeText(entry.event_year),
    headline: safeText(entry.headline) || "历史上的今天",
    summary: safeText(entry.summary),
    optionalNote: safeText(entry.optional_note),
    statusText: safeText(source.status_message) || (!!source.available ? "可展开查看" : "整理中"),
    sourceLabel: safeText(entry.source_label),
    cacheHit: !!source.cache_hit,
  };
}

Page({
  data: {
    monthCount: "0 天",
    currentStreak: "0 天",
    longestStreak: "0 天",
    journeyHeroLead: "记录中心",
    weekInsight: "本周摘要稍后更新",
    weekInsightStatus: "周摘要",
    todayHistory: buildTodayHistoryState(),
    recentItems: [],
    recentStatus: "最近记录",
    entryCards: [
      {
        key: "calendar",
        title: "情绪日历",
        subtitle: "按月回看",
        badge: "日历",
        tone: "calendar",
        featured: true,
        path: "/pages/calendar/index",
      },
      {
        key: "report",
        title: "周报复盘",
        subtitle: "本周洞察",
        badge: "周报",
        tone: "report",
        featured: false,
        path: "/pages/report/index",
      },
      {
        key: "history",
        title: "历史记录",
        subtitle: "全部记录",
        badge: "历史",
        tone: "history",
        featured: false,
        path: "/pages/history/index",
      },
    ],
  },

  onShow() {
    if (ensurePhase5Auth(JOURNEY_TAB)) return;
    setTabBarSelected(this, JOURNEY_TAB);
    this._todayHistoryFocusRequest = consumeTodayHistoryFocusRequest();
    this.loadJourneyHub({
      forceRefresh: !!this._todayHistoryFocusRequest,
    });
  },

  onPullDownRefresh() {
    this.loadJourneyHub({ forceRefresh: true }).finally(() => {
      wx.stopPullDownRefresh();
    });
  },

  async loadJourneyHub(options = {}) {
    const {
      calendarRes,
      reportRes,
      historyRes,
      todayHistoryRes,
    } = await getDashboardOverviewSnapshot({
      forceRefresh: !!(options && options.forceRefresh),
    });

    const nextData = {};

    if (calendarRes.status === "fulfilled") {
      const calendar = calendarRes.value || {};
      const checkedDays = Number(calendar.checked_days) || 0;
      const currentStreak = Number(calendar.current_streak) || 0;
      const longestStreak = Number(calendar.longest_streak) || 0;

      nextData.monthCount = `${checkedDays} 天`;
      nextData.currentStreak = `${currentStreak} 天`;
      nextData.longestStreak = `${longestStreak} 天`;
      nextData.journeyHeroLead = checkedDays ? "本月记录进行中" : "从今天开始记录";
    }

    if (reportRes.status === "fulfilled") {
      const report = reportRes.value || {};
      const dominant = Array.isArray(report.dominant_emotions) ? report.dominant_emotions[0] : null;
      const insight = safeText(report.insight) || "本周数据积累中。";
      nextData.weekInsight = insight;
      nextData.weekInsightStatus = dominant
        ? `高频主情绪：${safeText(dominant.label) || safeText(dominant.code) || "待识别"}`
        : safeText(report.insight)
          ? "已更新"
          : "积累中";
    } else {
      nextData.weekInsight = "周报暂不可用。";
      nextData.weekInsightStatus = "稍后重试";
    }

    if (historyRes.status === "fulfilled") {
      const history = historyRes.value || {};
      const allItems = Array.isArray(history.items) ? history.items : [];
      const items = allItems.slice(0, 3).map(toRecentItem);
      nextData.recentItems = items;
      nextData.recentStatus = items.length ? `最近 ${items.length} 条` : "暂无记录";
    } else {
      nextData.recentItems = [];
      nextData.recentStatus = "加载失败";
    }

    if (todayHistoryRes.status === "fulfilled") {
      const nextTodayHistory = normalizeTodayHistory(todayHistoryRes.value);
      if (this._todayHistoryFocusRequest && nextTodayHistory.available) {
        nextTodayHistory.expanded = true;
        nextTodayHistory.statusText = "刚更新";
      }
      nextData.todayHistory = nextTodayHistory;
    } else {
      nextData.todayHistory = {
        ...buildTodayHistoryState(),
        statusText: "历史内容暂不可用",
      };
    }

    this._todayHistoryFocusRequest = null;

    this.setData({
      ...nextData,
    });
  },

  openEntry(event) {
    const path = (event && event.currentTarget && event.currentTarget.dataset.path) || "";
    if (!path) return;
    wx.navigateTo({ url: path });
  },

  openRecent(event) {
    const historyId = (event && event.currentTarget && event.currentTarget.dataset.id) || "";
    if (!historyId) {
      wx.navigateTo({ url: "/pages/history/index" });
      return;
    }
    wx.navigateTo({
      url: `/pages/history/detail?id=${encodeURIComponent(historyId)}`,
    });
  },

  toggleTodayHistory() {
    const current = this.data.todayHistory || buildTodayHistoryState();
    if (!current.available) return;
    this.setData({
      todayHistory: {
        ...current,
        expanded: !current.expanded,
      },
    });
  },
});
