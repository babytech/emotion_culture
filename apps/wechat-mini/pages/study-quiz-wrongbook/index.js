const { getStudyQuizWrongbook } = require("../../services/api");

const PAGE_SIZE = 20;

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function formatDateTime(value) {
  const raw = safeText(value);
  if (!raw) return "未知时间";
  const normalized = raw.endsWith("Z") ? raw.replace("Z", "+00:00") : raw;
  const dateObj = new Date(normalized);
  if (Number.isNaN(dateObj.getTime())) {
    return raw.replace("T", " ").replace("Z", "");
  }
  const yyyy = dateObj.getFullYear();
  const mm = String(dateObj.getMonth() + 1).padStart(2, "0");
  const dd = String(dateObj.getDate()).padStart(2, "0");
  const hh = String(dateObj.getHours()).padStart(2, "0");
  const mi = String(dateObj.getMinutes()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd} ${hh}:${mi}`;
}

Page({
  data: {
    items: [],
    total: 0,
    nextOffset: 0,
    hasMore: false,
    isLoading: false,
    isLoadingMore: false,
    errorMsg: "",
  },

  onShow() {
    this.loadWrongbook({ reset: true });
  },

  onPullDownRefresh() {
    this.loadWrongbook({ reset: true }).finally(() => {
      wx.stopPullDownRefresh();
    });
  },

  onReachBottom() {
    if (this.data.hasMore) {
      this.loadMore();
    }
  },

  async loadWrongbook(options = {}) {
    const reset = !!options.reset;
    if (reset) {
      if (this.data.isLoading) return;
    } else if (this.data.isLoading || this.data.isLoadingMore || !this.data.hasMore) {
      return;
    }

    const offset = reset ? 0 : this.data.nextOffset;
    this.setData({
      errorMsg: "",
      isLoading: reset,
      isLoadingMore: !reset,
    });
    try {
      const response = await getStudyQuizWrongbook({
        limit: PAGE_SIZE,
        offset,
      });
      const fetched = Array.isArray(response && response.items)
        ? response.items.map((item) => ({
            wrongbookId: safeText(item && item.wrongbook_id),
            questionId: safeText(item && item.question_id),
            questionType: safeText(item && item.question_type) || "unknown",
            stem: safeText(item && item.stem) || "题干缺失",
            rightAnswer: safeText(item && item.right_answer) || "暂无",
            latestUserAnswer: safeText(item && item.latest_user_answer) || "未作答",
            wrongTimes: Math.max(0, Number(item && item.wrong_times) || 0),
            firstWrongAtText: formatDateTime(item && item.first_wrong_at),
            lastWrongAtText: formatDateTime(item && item.last_wrong_at),
          }))
        : [];

      const merged = reset ? fetched : this.data.items.concat(fetched);
      const total = Math.max(0, Number(response && response.total) || merged.length);
      const nextOffset = offset + fetched.length;
      const hasMore = nextOffset < total;

      this.setData({
        items: merged,
        total,
        nextOffset,
        hasMore,
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "错题本加载失败，请稍后重试。",
      });
    } finally {
      this.setData({
        isLoading: false,
        isLoadingMore: false,
      });
    }
  },

  loadMore() {
    this.loadWrongbook({ reset: false });
  },

  retryLoad() {
    this.loadWrongbook({ reset: true });
  },

  retryQuiz() {
    wx.switchTab({
      url: "/pages/study-quiz/index",
    });
  },
});
