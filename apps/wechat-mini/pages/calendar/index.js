const { getRetentionCalendar } = require("../../services/api");

const WEEKDAY_HEADERS = ["一", "二", "三", "四", "五", "六", "日"];

function toMonthText(dateObj) {
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  return `${yyyy}-${mm}`;
}

function monthLabel(monthText) {
  const [year, month] = (monthText || "").split("-");
  if (!year || !month) return monthText || "";
  return `${year} 年 ${Number(month)} 月`;
}

function parseMonth(monthText) {
  const [yearText, monthTextValue] = (monthText || "").split("-");
  const year = Number(yearText);
  const month = Number(monthTextValue);
  if (!year || !month) return new Date();
  return new Date(year, month - 1, 1);
}

function buildCellItem(raw) {
  const dateText = (raw && raw.date) || "";
  const day = Number((dateText.split("-")[2] || "0").replace(/^0+/, "")) || 0;
  const primaryEmotion = (raw && raw.primary_emotion) || {};
  const emotionLabel = (primaryEmotion && primaryEmotion.label) || "";
  const hasCheckin = !!(raw && raw.has_checkin);
  return {
    date: dateText,
    day,
    hasCheckin,
    statusClass: hasCheckin ? "checked" : "unchecked",
    emotionLabel,
    emotionShort: emotionLabel ? emotionLabel.slice(0, 2) : "",
    analysesCount: Number((raw && raw.analyses_count) || 0),
  };
}

Page({
  data: {
    isLoading: false,
    errorMsg: "",
    currentMonth: "",
    currentMonthLabel: "",
    weekdays: WEEKDAY_HEADERS,
    items: [],
    checkedDays: 0,
    totalDays: 0,
    checkedToday: false,
    checkedTodayClass: "today-miss",
    checkedTodayText: "今日未打卡",
    currentStreak: 0,
    longestStreak: 0,
  },

  onLoad() {
    const now = new Date();
    const month = toMonthText(now);
    this.setData({
      currentMonth: month,
      currentMonthLabel: monthLabel(month),
    });
    this.loadCalendar(month);
  },

  onShow() {
    if (this.data.currentMonth) {
      this.loadCalendar(this.data.currentMonth);
    }
  },

  async loadCalendar(month) {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });
    try {
      const result = await getRetentionCalendar(month);
      const items = Array.isArray(result.items) ? result.items.map(buildCellItem) : [];
      const resolvedMonth = (result && result.month) || month || this.data.currentMonth;
      this.setData({
        currentMonth: resolvedMonth,
        currentMonthLabel: monthLabel(resolvedMonth),
        items,
        checkedDays: Number(result && result.checked_days) || 0,
        totalDays: Number(result && result.total_days) || items.length,
        checkedToday: !!(result && result.checked_today),
        checkedTodayClass: result && result.checked_today ? "today-ok" : "today-miss",
        checkedTodayText: result && result.checked_today ? "今日已打卡" : "今日未打卡",
        currentStreak: Number(result && result.current_streak) || 0,
        longestStreak: Number(result && result.longest_streak) || 0,
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "加载日历失败，请稍后重试。",
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  shiftMonth(delta) {
    const dateObj = parseMonth(this.data.currentMonth);
    dateObj.setMonth(dateObj.getMonth() + delta);
    const nextMonth = toMonthText(dateObj);
    this.setData({
      currentMonth: nextMonth,
      currentMonthLabel: monthLabel(nextMonth),
    });
    this.loadCalendar(nextMonth);
  },

  goPrevMonth() {
    this.shiftMonth(-1);
  },

  goNextMonth() {
    this.shiftMonth(1);
  },

  retryLoad() {
    if (this.data.isLoading) return;
    const month = this.data.currentMonth || toMonthText(new Date());
    this.loadCalendar(month);
  },

  goReport() {
    wx.navigateTo({ url: "/pages/report/index" });
  },
});
