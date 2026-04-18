const { getStudyQuizPaper, submitStudyQuiz } = require("../../services/api");

const QUIZ_CONTEXT_STORAGE_KEY = "ec_latest_quiz_context_v1";

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function createSubmitToken() {
  const stamp = Date.now().toString(36);
  const rand = Math.random().toString(16).slice(2, 10);
  return `qst_${stamp}_${rand}`;
}

function showModalAsync(options = {}) {
  return new Promise((resolve) => {
    wx.showModal({
      ...options,
      success(res) {
        resolve(!!(res && res.confirm));
      },
      fail() {
        resolve(false);
      },
    });
  });
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
    answered: false,
  };
}

function isQuestionAnswered(question) {
  if (!question || !question.questionId) return false;
  if (question.type === "radio") return !!safeText(question.selectedRadio);
  if (question.type === "check") {
    return Array.isArray(question.selectedChecks) && question.selectedChecks.length > 0;
  }
  if (question.type === "fill") {
    return Array.isArray(question.fillValues) && question.fillValues.some((value) => safeText(value));
  }
  return false;
}

function hydrateQuestionAnswerState(question) {
  const next = { ...question };
  next.answered = isQuestionAnswered(next);
  return next;
}

function countAnswered(questions) {
  if (!Array.isArray(questions)) return 0;
  return questions.filter((question) => question && question.answered).length;
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
    unansweredQuestions: 0,
    progressPercent: 0,
    questions: [],
    currentIndex: 0,
    currentQuestion: null,
    submitToken: "",
  },

  onShow() {
    if (!this.data.paperId && !this.data.isLoading) {
      this.loadPaper();
    }
  },

  syncQuestionState(nextQuestions, nextIndex = this.data.currentIndex, options = {}) {
    const list = Array.isArray(nextQuestions) ? nextQuestions : [];
    const total = Number(this.data.totalQuestions) || list.length;
    const maxIndex = Math.max(0, list.length - 1);
    const safeIndex = Math.min(Math.max(0, Number(nextIndex) || 0), maxIndex);
    const hydrated = list.map((question) => hydrateQuestionAnswerState(question));
    const answered = countAnswered(hydrated);
    const unanswered = Math.max(0, total - answered);
    const progressPercent = total > 0 ? Math.max(0, Math.min(100, Math.round((answered / total) * 100))) : 0;

    const nextData = {
      questions: hydrated,
      currentIndex: safeIndex,
      currentQuestion: hydrated[safeIndex] || null,
      answeredQuestions: answered,
      unansweredQuestions: unanswered,
      progressPercent,
    };
    if (options.clearToken) {
      nextData.submitToken = "";
    }
    this.setData(nextData);
  },

  async loadPaper() {
    this.setData({
      isLoading: true,
      errorMsg: "",
    });
    try {
      const response = await getStudyQuizPaper("english");
      const questions = Array.isArray(response && response.questions) ? response.questions.map(normalizeQuestion) : [];
      const totalQuestions = Number(response && response.total_questions) || questions.length;
      this.setData({
        paperId: safeText(response && response.paper_id),
        paperTitle: safeText(response && response.title) || "英语伴学小测",
        paperCourse: safeText(response && response.course) || "english",
        paperVersion: safeText(response && response.version),
        totalQuestions,
      });
      this.syncQuestionState(questions, 0, { clearToken: true });
    } catch (err) {
      this.setData({
        errorMsg: (err && err.message) || "加载小测试卷失败，请稍后重试。",
      });
    } finally {
      this.setData({ isLoading: false });
    }
  },

  updateAnsweredCount(nextQuestions) {
    this.syncQuestionState(nextQuestions, this.data.currentIndex, { clearToken: true });
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

  jumpToQuestion(event) {
    const index = Number(event && event.currentTarget && event.currentTarget.dataset.index);
    if (!Number.isFinite(index)) return;
    this.syncQuestionState(this.data.questions, index);
  },

  handlePrevQuestion() {
    if (this.data.currentIndex <= 0) return;
    this.syncQuestionState(this.data.questions, this.data.currentIndex - 1);
  },

  handleNextQuestion() {
    const total = Number(this.data.totalQuestions) || (this.data.questions || []).length;
    if (this.data.currentIndex >= total - 1) return;
    this.syncQuestionState(this.data.questions, this.data.currentIndex + 1);
  },

  buildSubmitPayload(submitToken) {
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
      submit_token: submitToken || undefined,
      answers,
    };
  },

  async submitQuiz() {
    if (this.data.isSubmitting || this.data.isLoading) return;

    if ((Number(this.data.answeredQuestions) || 0) <= 0) {
      const msg = "请先完成至少 1 题后再提交。";
      this.setData({ errorMsg: msg });
      wx.showToast({
        title: "请先作答",
        icon: "none",
      });
      return;
    }

    const unanswered = Number(this.data.unansweredQuestions) || 0;
    if (unanswered > 0) {
      const confirmed = await showModalAsync({
        title: "还有未答题",
        content: `当前还有 ${unanswered} 题未作答，确认现在提交吗？`,
        confirmText: "继续提交",
        cancelText: "继续答题",
      });
      if (!confirmed) return;
    }

    const submitToken = this.data.submitToken || createSubmitToken();
    if (!this.data.submitToken) {
      this.setData({ submitToken });
    }
    const payload = this.buildSubmitPayload(submitToken);

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
