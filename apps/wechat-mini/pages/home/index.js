const {
  getCheckinStatus,
  getRetentionCalendar,
  getRetentionWeeklyReport,
  getTodayHistory,
  listFavorites,
  listHistory,
} = require("../../services/api");
const { ensurePhase5Auth } = require("../../utils/auth-gate");
const { consumeTodayHistoryFocusRequest } = require("../../utils/today-history-focus");
const { ANALYZE_TAB, FAVORITES_TAB, HOME_TAB, JOURNEY_TAB, PROFILE_TAB, setTabBarSelected } = require("../../utils/tabbar");

const HOME_ACTIONS = [
  { key: "quiz", icon: "测", title: "伴学小测" },
  { key: "journey", icon: "记", title: "记录中心" },
  { key: "analyze", icon: "析", title: "快速分析" },
  { key: "checkin", icon: "签", title: "每日签到" },
  { key: "profile", icon: "我", title: "我的空间" },
];

function toMonthText(dateObj) {
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  return `${yyyy}-${mm}`;
}

function toDateText(dateObj) {
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  const dd = String(dateObj.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function toTodayLabel(dateObj) {
  const source = dateObj instanceof Date ? dateObj : new Date();
  const month = source.getMonth() + 1;
  const day = source.getDate();
  const weekday = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"][source.getDay()];
  return `${month}月${day}日 · ${weekday}`;
}

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function toDisplayTime(value) {
  const raw = safeText(value);
  if (!raw) return "尚未记录";
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

function toPrimaryEmotionLabel(item) {
  const primaryEmotion = (item && item.primary_emotion) || {};
  return safeText(primaryEmotion.label) || safeText(primaryEmotion.code) || "暂未识别";
}

function toPrimaryEmotionCode(item) {
  const primaryEmotion = (item && item.primary_emotion) || {};
  return safeText(primaryEmotion.code).toLowerCase();
}

function toSecondaryText(items) {
  if (!Array.isArray(items) || items.length === 0) return "暂无补充情绪";
  const labels = [];
  items.forEach((item) => {
    const label = safeText(item && (item.label || item.code));
    if (label && !labels.includes(label)) labels.push(label);
  });
  return labels.length ? labels.join("、") : "暂无补充情绪";
}

function toHistoryPreview(item) {
  if (!item) return null;
  return {
    historyId: safeText(item.history_id),
    displayTime: toDisplayTime(item.analyzed_at),
    primaryEmotionCode: toPrimaryEmotionCode(item),
    primaryEmotionLabel: toPrimaryEmotionLabel(item),
    secondaryEmotionText: toSecondaryText(item.secondary_emotions),
    summary: safeText(item.emotion_overview_summary) || "本次结果暂无摘要。",
  };
}

function toFavoritePreview(item) {
  const type = safeText(item && item.favorite_type);
  const typeLabel = type === "poem" ? "诗词" : type === "guochao" ? "国潮" : "收藏";
  return {
    favoriteId: safeText(item && item.favorite_id),
    typeLabel,
    title: safeText(item && item.title) || "未命名收藏",
    subtitle: safeText(item && item.subtitle) || "稍后到收藏页查看完整内容",
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

function toHeroTheme(emotionCode, emotionLabel) {
  const code = safeText(emotionCode).toLowerCase();
  const label = safeText(emotionLabel);

  if (code === "sad" || /悲伤|难过|低落|沮丧/.test(label)) return "sad";
  if (code === "neutral" || /平静|平和|宁静/.test(label)) return "calm";
  if (code === "happy" || /高兴|开心|快乐|愉快/.test(label)) return "happy";
  if (code === "angry" || /生气|愤怒|烦躁/.test(label)) return "angry";
  if (code === "fear" || /恐惧|害怕|担忧|焦虑/.test(label)) return "fear";
  if (code === "surprise" || /惊讶|惊喜/.test(label)) return "surprise";
  return "warm";
}

function normalizeCheckin(raw) {
  const source = raw && typeof raw === "object" ? raw : {};
  return {
    signedToday: !!source.signed_today,
    currentStreak: Math.max(0, Number(source.current_streak) || 0),
    pointsBalance: Math.max(0, Number(source.points_balance) || 0),
    dailyPoints: Math.max(0, Number(source.daily_points) || 0),
    message: safeText(source.message) || "每日签到可获得积分",
  };
}

Page({
  data: {
    isRefreshing: false,
    todayLabel: toTodayLabel(new Date()),
    heroEmotion: "还没有今天的记录",
    heroTheme: "warm",
    heroStreak: "0 天",
    heroMonthCount: "0 天",
    heroLatestTime: "等待你开始今天的第一条记录",
    weekInsightText: "本周洞察稍后更新",
    weekInsightStatus: "等待周报数据",
    favoritePreview: [],
    recentRecord: null,
    recentRecordStatus: "还没有最近一次结果",
    todayHistory: buildTodayHistoryState(),
    quickActions: HOME_ACTIONS,
    checkin: normalizeCheckin({}),
  },

  onShow() {
    if (ensurePhase5Auth(HOME_TAB)) return;
    setTabBarSelected(this, HOME_TAB);
    this._todayHistoryFocusRequest = consumeTodayHistoryFocusRequest();
    this.loadDashboard();
  },

  async loadDashboard() {
    this.setData({ isRefreshing: true });

    const [calendarRes, reportRes, historyRes, favoritesRes, todayHistoryRes, checkinRes] = await Promise.allSettled([
      getRetentionCalendar(toMonthText(new Date())),
      getRetentionWeeklyReport(),
      listHistory({ limit: 5, offset: 0 }),
      listFavorites({ limit: 2, offset: 0 }),
      getTodayHistory(toDateText(new Date())),
      getCheckinStatus(),
    ]);

    const nextData = {};

    if (calendarRes.status === "fulfilled") {
      const calendar = calendarRes.value || {};
      nextData.heroStreak = `${Number(calendar.current_streak) || 0} 天`;
      nextData.heroMonthCount = `${Number(calendar.checked_days) || 0} 天`;
    }

    if (reportRes.status === "fulfilled") {
      const report = reportRes.value || {};
      const dominant = Array.isArray(report.dominant_emotions) ? report.dominant_emotions[0] : null;
      nextData.weekInsightText = safeText(report.insight) || "本周还在积累新的洞察。";
      nextData.weekInsightStatus = dominant
        ? `高频主情绪：${safeText(dominant.label) || safeText(dominant.code) || "待识别"}`
        : "洞察已更新";
    } else {
      nextData.weekInsightText = "周报接口暂时不可用，稍后自动重试。";
      nextData.weekInsightStatus = "稍后重试";
    }

    if (historyRes.status === "fulfilled") {
      const history = historyRes.value || {};
      const recent = Array.isArray(history.items) ? history.items[0] : null;
      const recentPreview = toHistoryPreview(recent);
      nextData.recentRecord = recentPreview;
      nextData.recentRecordStatus = recentPreview ? "最近一次分析结果" : "完成一次分析后，这里会出现摘要";
      nextData.heroEmotion = recentPreview ? recentPreview.primaryEmotionLabel : "还没有今天的记录";
      nextData.heroTheme = recentPreview
        ? toHeroTheme(recentPreview.primaryEmotionCode, recentPreview.primaryEmotionLabel)
        : "warm";
      nextData.heroLatestTime = recentPreview
        ? `最近一次更新于 ${recentPreview.displayTime}`
        : "等待你开始今天的第一条记录";
    } else {
      nextData.recentRecord = null;
      nextData.recentRecordStatus = "历史接口暂不可用";
      nextData.heroTheme = "warm";
    }

    if (favoritesRes.status === "fulfilled") {
      const favorites = favoritesRes.value || {};
      const items = Array.isArray(favorites.items) ? favorites.items.map(toFavoritePreview) : [];
      nextData.favoritePreview = items;
    } else {
      nextData.favoritePreview = [];
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

    if (checkinRes.status === "fulfilled") {
      nextData.checkin = normalizeCheckin(checkinRes.value);
    }

    this._todayHistoryFocusRequest = null;

    this.setData({
      ...nextData,
      isRefreshing: false,
    });
  },

  handleQuickAction(event) {
    const key = safeText(event && event.currentTarget && event.currentTarget.dataset.key);
    if (!key) return;
    if (key === "quiz") {
      this.openStudyQuizPage();
      return;
    }
    if (key === "journey") {
      this.openJourneyTab();
      return;
    }
    if (key === "analyze") {
      this.openAnalyzeTab();
      return;
    }
    if (key === "checkin") {
      this.openCheckinPage();
      return;
    }
    if (key === "profile") {
      this.openProfileTab();
    }
  },

  openAnalyzeTab() {
    wx.switchTab({ url: ANALYZE_TAB });
  },

  openStudyQuizPage() {
    wx.navigateTo({ url: "/pages/study-quiz/index" });
  },

  openCheckinPage() {
    wx.navigateTo({ url: "/pages/checkin/index" });
  },

  openRecentRecord() {
    const recent = this.data.recentRecord;
    if (!recent || !recent.historyId) {
      wx.switchTab({ url: ANALYZE_TAB });
      return;
    }
    wx.navigateTo({
      url: `/pages/history/detail?id=${encodeURIComponent(recent.historyId)}`,
    });
  },

  openFavoritesTab() {
    wx.switchTab({ url: FAVORITES_TAB });
  },

  openJourneyTab() {
    wx.switchTab({ url: JOURNEY_TAB });
  },

  openProfileTab() {
    wx.switchTab({ url: PROFILE_TAB });
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
