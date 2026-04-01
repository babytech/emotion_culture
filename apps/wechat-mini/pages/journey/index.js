const { getRetentionCalendar, getRetentionWeeklyReport, listHistory } = require("../../services/api");
const { JOURNEY_TAB, setTabBarSelected } = require("../../utils/tabbar");

function toMonthText(dateObj) {
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  return `${yyyy}-${mm}`;
}

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

Page({
  data: {
    monthCount: "0 天",
    currentStreak: "0 天",
    longestStreak: "0 天",
    journeyHeroLead: "从第一次记录开始，这里会慢慢长出你的情绪轨迹。",
    journeyHeroNote: "开始记录后，你会逐渐看见自己的节奏。",
    weekInsight: "本周摘要稍后更新",
    weekInsightStatus: "等待周报数据",
    recentItems: [],
    recentStatus: "最近记录预览",
    entryCards: [
      {
        key: "calendar",
        title: "情绪日历",
        subtitle: "按月回看打卡与主情绪",
        badge: "月视图",
        tone: "calendar",
        featured: true,
        path: "/pages/calendar/index",
      },
      {
        key: "report",
        title: "周报复盘",
        subtitle: "回看这一周的洞察与建议",
        badge: "周摘要",
        tone: "report",
        featured: false,
        path: "/pages/report/index",
      },
      {
        key: "history",
        title: "历史记录",
        subtitle: "查看全部摘要与详情",
        badge: "全记录",
        tone: "history",
        featured: false,
        path: "/pages/history/index",
      },
    ],
  },

  onShow() {
    setTabBarSelected(this, JOURNEY_TAB);
    this.loadJourneyHub();
  },

  async loadJourneyHub() {
    const [calendarRes, reportRes, historyRes] = await Promise.allSettled([
      getRetentionCalendar(toMonthText(new Date())),
      getRetentionWeeklyReport(),
      listHistory({ limit: 3, offset: 0 }),
    ]);

    const nextData = {};

    if (calendarRes.status === "fulfilled") {
      const calendar = calendarRes.value || {};
      const checkedDays = Number(calendar.checked_days) || 0;
      const currentStreak = Number(calendar.current_streak) || 0;
      const longestStreak = Number(calendar.longest_streak) || 0;

      nextData.monthCount = `${checkedDays} 天`;
      nextData.currentStreak = `${currentStreak} 天`;
      nextData.longestStreak = `${longestStreak} 天`;
      nextData.journeyHeroLead = checkedDays
        ? currentStreak
          ? `这个月已经记录 ${checkedDays} 天，连续 ${currentStreak} 天。`
          : `这个月已经留下 ${checkedDays} 天的情绪痕迹。`
        : "从第一次记录开始，这里会慢慢长出你的情绪轨迹。";
      nextData.journeyHeroNote = longestStreak
        ? `最长连续 ${longestStreak} 天，记录节奏正在慢慢形成。`
        : "开始记录后，你会逐渐看见自己的节奏。";
    }

    if (reportRes.status === "fulfilled") {
      const report = reportRes.value || {};
      const dominant = Array.isArray(report.dominant_emotions) ? report.dominant_emotions[0] : null;
      const insight = safeText(report.insight) || "本周还在持续沉淀新的洞察。";
      nextData.weekInsight = insight;
      nextData.weekInsightStatus = dominant
        ? `高频主情绪：${safeText(dominant.label) || safeText(dominant.code) || "待识别"}`
        : safeText(report.insight)
          ? "已生成"
          : "积累中";
    } else {
      nextData.weekInsight = "周报接口失败时，记录中枢仍保留分发入口。";
      nextData.weekInsightStatus = "稍后重试";
    }

    if (historyRes.status === "fulfilled") {
      const history = historyRes.value || {};
      const items = Array.isArray(history.items) ? history.items.map(toRecentItem) : [];
      nextData.recentItems = items;
      nextData.recentStatus = items.length ? "最近 3 条记录" : "完成一次分析后会出现";
    } else {
      nextData.recentItems = [];
      nextData.recentStatus = "历史接口暂不可用";
    }

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
});
