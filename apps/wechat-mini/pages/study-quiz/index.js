const { getStudyQuizPaper, submitStudyQuiz } = require("../../services/api");

const QUIZ_CONTEXT_STORAGE_KEY = "ec_latest_quiz_context_v1";

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeQuestion(raw) {
  const questionType = safeText(raw && raw.type);
  const options = Array.isArray(raw && raw.options)
    ? raw.options.map((item) => ({
        item: safeText(item && item.item),
        content: safeText(item && item.content),
        selected: false,
      }))
    : [];
  const fills = Array.isArray(raw && raw.fills) ? raw.fills : [];
  return {
    questionId: safeText(raw && raw.question_id),
    type: questionType,
    stem: safeText(raw && raw.stem),
    options,
    fills,
    selectedRadio: "",
    selectedChecks: [],
    fillValues: fills.length ? fills.map(() => "") : [""],
  };
}

function countAnswered(questions) {
  if (!Array.isArray(questions)) return 0;
  let count = 0;
  questions.forEach((item) => {
    if (!item || !item.questionId) return;
    if (item.type === "radio" && safeText(item.selectedRadio)) {
      count += 1;
      return;
    }
    if (item.type === "check" && Array.isArray(item.selectedChecks) && item.selectedChecks.length > 0) {
      count += 1;
      return;
    }
    if (item.type === "fill") {
      const hasValue = Array.isArray(item.fillValues) && item.fillValues.some((value) => safeText(value));
      if (hasValue) count += 1;
    }
  });
  return count;
}

Page({
  data: {
    isLoading: false,
    isSubmitting: false,
    errorMsg: "",
    paperId: "",
    paperTitle: "",
    paperCourse: "english",
    paperVersion: "",
    totalQuestions: 0,
    answeredQuestions: 0,
    questions: [],
  },

  onShow() {
    if (!this.data.paperId && !this.data.isLoading) {
      this.loadPaper();
    }
  },

  async loadPaper() {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });
    try {
      const response = await getStudyQuizPaper("english");
      const questions = Array.isArray(response && response.questions) ? response.questions.map(normalizeQuestion) : [];
      this.setData({
        paperId: safeText(response && response.paper_id),
        paperTitle: safeText(response && response.title) || "英语伴学小测",
        paperCourse: safeText(response && response.course) || "english",
        paperVersion: safeText(response && response.version),
        totalQuestions: Number(response && response.total_questions) || questions.length,
        answeredQuestions: 0,
        questions,
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "加载小测试卷失败，请稍后重试。",
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  updateAnsweredCount(nextQuestions) {
    this.setData({
      questions: nextQuestions,
      answeredQuestions: countAnswered(nextQuestions),
    });
  },

  handleRadioChange(event) {
    const questionId = safeText(event && event.currentTarget && event.currentTarget.dataset.qid);
    const optionItem = safeText(event && event.currentTarget && event.currentTarget.dataset.option);
    if (!questionId || !optionItem) return;

    const nextQuestions = (this.data.questions || []).map((item) => {
      if (item.questionId !== questionId) return item;
      return {
        ...item,
        selectedRadio: optionItem,
      };
    });
    this.updateAnsweredCount(nextQuestions);
  },

  handleCheckToggle(event) {
    const questionId = safeText(event && event.currentTarget && event.currentTarget.dataset.qid);
    const optionItem = safeText(event && event.currentTarget && event.currentTarget.dataset.option);
    if (!questionId || !optionItem) return;

    const nextQuestions = (this.data.questions || []).map((item) => {
      if (item.questionId !== questionId) return item;
      const options = Array.isArray(item.options) ? item.options.map((option) => ({ ...option })) : [];
      options.forEach((option) => {
        if ((option.item || "") === optionItem) {
          option.selected = !option.selected;
        }
      });
      const selected = options
        .filter((option) => option.selected)
        .map((option) => option.item)
        .sort();
      return {
        ...item,
        options,
        selectedChecks: selected,
      };
    });
    this.updateAnsweredCount(nextQuestions);
  },

  handleFillInput(event) {
    const questionId = safeText(event && event.currentTarget && event.currentTarget.dataset.qid);
    const fillIndex = Number(event && event.currentTarget && event.currentTarget.dataset.idx);
    const value = (event && event.detail && event.detail.value) || "";
    if (!questionId || !Number.isFinite(fillIndex)) return;

    const nextQuestions = (this.data.questions || []).map((item) => {
      if (item.questionId !== questionId) return item;
      const values = Array.isArray(item.fillValues) ? [...item.fillValues] : [""];
      values[fillIndex] = value;
      return {
        ...item,
        fillValues: values,
      };
    });
    this.updateAnsweredCount(nextQuestions);
  },

  buildSubmitPayload() {
    const answers = [];
    (this.data.questions || []).forEach((item) => {
      if (!item || !item.questionId) return;
      if (item.type === "radio") {
        answers.push({
          question_id: item.questionId,
          answer: safeText(item.selectedRadio),
        });
        return;
      }
      if (item.type === "check") {
        answers.push({
          question_id: item.questionId,
          answer: Array.isArray(item.selectedChecks) ? item.selectedChecks : [],
        });
        return;
      }
      answers.push({
        question_id: item.questionId,
        answer: Array.isArray(item.fillValues) ? item.fillValues.map((value) => safeText(value)) : [],
      });
    });
    return {
      course: this.data.paperCourse || "english",
      paper_id: this.data.paperId || undefined,
      answers,
    };
  },

  async submitQuiz() {
    if (this.data.isSubmitting || this.data.isLoading) return;
    const payload = this.buildSubmitPayload();
    this.setData({
      isSubmitting: true,
      errorMsg: "",
    });
    wx.showLoading({ title: "判分中..." });
    try {
      const response = await submitStudyQuiz(payload);
      const summary = (response && response.quiz_record) || {};
      const quizRecordId = safeText(summary.quiz_record_id);
      try {
        wx.setStorageSync(QUIZ_CONTEXT_STORAGE_KEY, response);
      } catch (err) {
        // ignore
      }
      wx.navigateTo({
        url: `/pages/study-quiz-result/index?quiz_record_id=${encodeURIComponent(quizRecordId)}&from=submit`,
      });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "提交失败，请稍后重试。",
      });
    } finally {
      wx.hideLoading();
      this.setData({ isSubmitting: false });
    }
  },

  goAnalyzeDirectly() {
    wx.switchTab({ url: "/pages/analyze/index" });
  },
});
