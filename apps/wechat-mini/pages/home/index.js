const {
  getRetentionCalendar,
  getRetentionWeeklyReport,
  listFavorites,
  listHistory,
} = require("../../services/api");
const { ensurePhase5Auth } = require("../../utils/auth-gate");
const { ANALYZE_TAB, FAVORITES_TAB, HOME_TAB, PROFILE_TAB, setTabBarSelected } = require("../../utils/tabbar");

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
    hint: typeLabel === "诗词" ? "保留了当时最打动你的诗意回应" : typeLabel === "国潮" ? "保留了当时生成的视觉慰藉内容" : "已加入你的个人收藏夹",
  };
}

function buildMetrics(values) {
  const source = values || {};
  return [
    {
      label: "最近历史",
      caption: "最近一条记录时间",
      value: source.recentHistory || "暂无",
    },
    {
      label: "本周洞察",
      caption: "本周状态摘要",
      value: source.weekInsight || "待更新",
    },
  ];
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

Page({
  data: {
    isRefreshing: false,
    heroEmotion: "还没有今天的记录",
    heroTheme: "warm",
    heroStreak: "0 天",
    heroMonthCount: "0 天",
    heroLatestTime: "等待你开始今天的第一条记录",
    metrics: buildMetrics(),
    weekInsightText: "本周洞察稍后更新",
    weekInsightStatus: "等待周报数据",
    favoriteStatusText: "加载后会显示最近收藏预览",
    favoritePreview: [],
    recentRecord: null,
    recentRecordStatus: "还没有最近一次结果",
  },

  onShow() {
    if (ensurePhase5Auth(HOME_TAB)) return;
    setTabBarSelected(this, HOME_TAB);
    this.loadDashboard();
  },

  async loadDashboard() {
    this.setData({ isRefreshing: true });

    const [calendarRes, reportRes, historyRes, favoritesRes] = await Promise.allSettled([
      getRetentionCalendar(toMonthText(new Date())),
      getRetentionWeeklyReport(),
      listHistory({ limit: 5, offset: 0 }),
      listFavorites({ limit: 3, offset: 0 }),
    ]);

    const nextData = {};
    const nextMetrics = {
      recentHistory: this.data.metrics[0] ? this.data.metrics[0].value : "暂无",
      weekInsight: this.data.metrics[1] ? this.data.metrics[1].value : "待更新",
    };

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
      nextMetrics.weekInsight = safeText(report.insight) ? "已生成" : "积累中";
    } else {
      nextData.weekInsightText = "周报接口暂时不可用，首页保留其它入口。";
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
      nextMetrics.recentHistory = recentPreview ? recentPreview.displayTime : "暂无";
    } else {
      nextData.recentRecordStatus = "历史接口暂不可用";
      nextData.heroTheme = "warm";
    }

    if (favoritesRes.status === "fulfilled") {
      const favorites = favoritesRes.value || {};
      const items = Array.isArray(favorites.items) ? favorites.items.map(toFavoritePreview) : [];
      nextData.favoritePreview = items;
      nextData.favoriteStatusText = items.length ? "最近收藏预览" : "你还没有收藏内容";
    } else {
      nextData.favoriteStatusText = "收藏接口暂不可用";
      nextData.favoritePreview = [];
    }

    this.setData({
      ...nextData,
      metrics: buildMetrics(nextMetrics),
      isRefreshing: false,
    });
  },

  openAnalyzeTab() {
    wx.switchTab({ url: ANALYZE_TAB });
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

  openProfileTab() {
    wx.switchTab({ url: PROFILE_TAB });
  },
});
