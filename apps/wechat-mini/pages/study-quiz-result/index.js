const { getStudyQuizHistoryDetail } = require("../../services/api");

const QUIZ_CONTEXT_STORAGE_KEY = "ec_latest_quiz_context_v1";
const ANALYZE_ENTRY_CONTEXT_STORAGE_KEY = "ec_analyze_entry_context_v1";

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function courseLabel(course) {
  const normalized = safeText(course).toLowerCase();
  if (normalized === "english") return "英语";
  return normalized || "课程";
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

function scoreTone(score) {
  const value = Number(score) || 0;
  if (value >= 85) return "good";
  if (value >= 60) return "normal";
  return "low";
}

function buildViewData(response) {
  const quizRecord = (response && response.quiz_record) || {};
  const results = Array.isArray(response && response.results) ? response.results : [];
  const wrongItems = Array.isArray(response && response.wrong_items) ? response.wrong_items : [];
  const totalQuestions = Number(quizRecord.total_questions) || results.length || 0;
  const correctCount = Number(quizRecord.correct_count) || 0;
  const score = Number(quizRecord.score) || 0;
  const answered = Number(quizRecord.answered_questions) || 0;
  const correctRate = totalQuestions > 0 ? `${Math.round((correctCount / totalQuestions) * 100)}%` : "0%";
  return {
    hasData: !!safeText(quizRecord.quiz_record_id),
    summary: {
      quizRecordId: safeText(quizRecord.quiz_record_id),
      course: safeText(quizRecord.course) || "english",
      courseLabel: courseLabel(quizRecord.course),
      score,
      grade: safeText(quizRecord.grade) || "C",
      totalQuestions,
      answeredQuestions: answered,
      correctCount,
      wrongCount: Number(quizRecord.wrong_count) || wrongItems.length,
      partialCount: Number(quizRecord.partial_count) || 0,
      submittedAt: safeText(quizRecord.submitted_at),
      submittedAtText: formatDateTime(quizRecord.submitted_at),
      correctRate,
      scoreTone: scoreTone(score),
    },
    results,
    wrongItems,
    nextActionHint:
      safeText(response && response.next_action_hint) || "小测完成后，去做一次情绪分析会更有帮助。",
  };
}

function readCachedContext() {
  try {
    return wx.getStorageSync(QUIZ_CONTEXT_STORAGE_KEY);
  } catch (err) {
    return null;
  }
}

Page({
  data: {
    quizRecordId: "",
    isLoading: false,
    errorMsg: "",
    hasData: false,
    summary: null,
    results: [],
    wrongItems: [],
    nextActionHint: "",
  },

  onLoad(options) {
    const quizRecordId = safeText(options && decodeURIComponent(options.quiz_record_id || ""));
    this.setData({ quizRecordId });
  },

  onShow() {
    this.loadQuizResult();
  },

  async loadQuizResult() {
    const quizRecordId = this.data.quizRecordId;
    if (!quizRecordId) {
      this.setData({ errorMsg: "缺少小测记录 ID。" });
      return;
    }

    this.setData({
      isLoading: true,
      errorMsg: "",
    });
    try {
      const cached = readCachedContext();
      const cachedQuizRecordId = safeText(cached && cached.quiz_record && cached.quiz_record.quiz_record_id);
      const response = cached && cachedQuizRecordId === quizRecordId ? cached : await getStudyQuizHistoryDetail(quizRecordId);
      const nextData = buildViewData(response);
      this.setData({
        ...nextData,
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "加载小测结果失败，请稍后重试。",
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  goAnalyzeWithQuizContext() {
    const summary = this.data.summary || {};
    const quizRecordId = safeText(summary.quizRecordId);
    if (!quizRecordId) return;

    try {
      wx.setStorageSync(ANALYZE_ENTRY_CONTEXT_STORAGE_KEY, {
        source: "study_quiz",
        quiz_record_id: quizRecordId,
        quiz_score: Number(summary.score) || 0,
        quiz_grade: safeText(summary.grade),
        quiz_course: safeText(summary.course),
        from_page: "study_quiz_result",
        at: new Date().toISOString(),
      });
    } catch (err) {
      // ignore
    }

    wx.switchTab({
      url: "/pages/analyze/index",
    });
  },

  retryQuiz() {
    wx.navigateTo({
      url: "/pages/study-quiz/index",
    });
  },

  goWrongbook() {
    wx.navigateTo({
      url: "/pages/study-quiz-wrongbook/index",
    });
  },
});
