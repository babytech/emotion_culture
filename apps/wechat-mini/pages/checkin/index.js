const { getCheckinStatus, signInDaily } = require("../../services/api");

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeDay(day) {
  const state = safeText(day && day.state) || "pending";
  return {
    dayIndex: Number(day && day.day_index) || 0,
    label: safeText(day && day.label) || "",
    points: Number(day && day.points) || 0,
    state,
    isDone: state === "done",
    isCurrent: state === "current",
  };
}

function normalizeStatus(raw) {
  const source = raw && typeof raw === "object" ? raw : {};
  const days = Array.isArray(source.days) ? source.days.map(normalizeDay) : [];
  return {
    today: safeText(source.today),
    signedToday: !!source.signed_today,
    currentStreak: Math.max(0, Number(source.current_streak) || 0),
    totalSignedDays: Math.max(0, Number(source.total_signed_days) || 0),
    dailyPoints: Math.max(0, Number(source.daily_points) || 0),
    pointsBalance: Math.max(0, Number(source.points_balance) || 0),
    message: safeText(source.message) || "完成签到后可获得积分。",
    days,
  };
}

Page({
  data: {
    isLoading: false,
    isSigning: false,
    errorMsg: "",
    status: normalizeStatus({}),
    awardPreviewDays: [],
    awardModalVisible: false,
    awardPoints: 0,
  },

  onShow() {
    this.loadStatus();
  },

  async loadStatus() {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });
    try {
      const response = await getCheckinStatus();
      const status = normalizeStatus(response);
      this.setData({
        status,
        awardPreviewDays: status.days.slice(0, 3),
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "加载签到状态失败，请稍后重试。",
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  async handleSignIn() {
    if (this.data.isSigning || this.data.isLoading) return;
    const current = this.data.status || {};
    if (current.signedToday) {
      wx.showToast({
        title: "今天已经签到了",
        icon: "none",
      });
      return;
    }

    this.setData({
      isSigning: true,
      errorMsg: "",
    });

    try {
      const response = await signInDaily();
      const status = normalizeStatus(response && response.status);
      const awardedPoints = Math.max(0, Number(response && response.awarded_points) || 0);
      this.setData({
        status,
        awardPreviewDays: status.days.slice(0, 3),
        awardPoints: awardedPoints,
        awardModalVisible: !!(response && response.just_signed && awardedPoints > 0),
      });
      wx.showToast({
        title: awardedPoints > 0 ? `签到成功 +${awardedPoints}` : "签到成功",
        icon: "none",
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "签到失败，请稍后重试。",
      });
      wx.showToast({
        title: "签到失败",
        icon: "none",
      });
    } finally {
      this.setData({ isSigning: false });
    }
  },

  closeAwardModal() {
    this.setData({
      awardModalVisible: false,
    });
  },

  openRuleHint() {
    wx.showModal({
      title: "签到规则",
      content: "每天可签到 1 次，成功后获得固定积分。连续签到会累计连续天数，漏签将从第1天重新开始。",
      confirmText: "知道了",
      showCancel: false,
    });
  },
});
