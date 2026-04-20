const { getStudyQuizPaper, submitStudyQuiz } = require("../../services/api");
const { ensurePhase5Auth } = require("../../utils/auth-gate");
const { QUIZ_TAB, setTabBarSelected } = require("../../utils/tabbar");
const {
  isValidQuizPaperPayload,
  readQuizPaperCache,
  writeQuizPaperCache,
} = require("../../utils/study-quiz-paper-cache");
const { getQuizCourseOptions, getQuizCourseLabel, normalizeQuizCourse } = require("../../utils/study-quiz-course");

const QUIZ_CONTEXT_STORAGE_KEY = "ec_latest_quiz_context_v1";
const QUIZ_DRAFT_STORAGE_KEY = "ec_study_quiz_draft_v1";
const QUIZ_DRAFT_MAX_AGE_MS = 3 * 24 * 60 * 60 * 1000;
const QUIZ_DURATION_OPTIONS = [10, 20, 30, 45, 60];

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function createSubmitToken() {
  const stamp = Date.now().toString(36);
  const rand = Math.random().toString(16).slice(2, 10);
  return `qst_${stamp}_${rand}`;
}

function formatDurationLabel(minutes) {
  return `${Math.max(1, Number(minutes) || 1)} 分钟`;
}

function formatCountdown(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const mm = String(Math.floor(safeSeconds / 60)).padStart(2, "0");
  const ss = String(safeSeconds % 60).padStart(2, "0");
  return `${mm}:${ss}`;
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

function isValidPaperPayload(payload) {
  return isValidQuizPaperPayload(payload);
}

function readCachedPaper(course) {
  return readQuizPaperCache({
    course: normalizeQuizCourse(course),
  });
}

function writeCachedPaper(paper, course) {
  writeQuizPaperCache(paper, {
    course: normalizeQuizCourse(course),
  });
}

function mapPaperLoadError(err) {
  const message = safeText(err && err.message);
  if (!message) {
    return "试卷加载失败，请重试。";
  }
  const lower = message.toLowerCase();
  if (
    lower.includes("102002") ||
    lower.includes("timeout") ||
    lower.includes("timed out") ||
    lower.includes("request:fail")
  ) {
    return "网络波动导致加载超时，请点“重试加载”。";
  }
  if (message.length > 88) {
    return "试卷加载失败，请稍后重试。";
  }
  return message;
}

function isSubmitRetryableError(err) {
  const message = safeText(err && err.message).toLowerCase();
  if (!message) return false;
  return (
    message.includes("102002") ||
    message.includes("timeout") ||
    message.includes("timed out") ||
    message.includes("request:fail") ||
    message.includes("network") ||
    message.includes("connection") ||
    message.includes("econn")
  );
}

function mapSubmitError(err) {
  const message = safeText(err && err.message);
  if (!message) return "提交失败，请稍后重试。";
  const lower = message.toLowerCase();
  if (lower.includes("quiz_paper_mismatch")) {
    return "题目已更新，请重新开始测试。";
  }
  if (isSubmitRetryableError(err)) {
    return "网络波动导致提交超时，请再次点击提交。";
  }
  if (message.length > 88) {
    return "提交失败，请稍后重试。";
  }
  return message;
}

function withClientTimeout(promise, timeoutMs, timeoutMessage) {
  return new Promise((resolve, reject) => {
    const timeout = Math.max(3000, Number(timeoutMs) || 15000);
    let finished = false;
    const timer = setTimeout(() => {
      if (finished) return;
      finished = true;
      reject(new Error(timeoutMessage || "请求超时，请重试。"));
    }, timeout);

    Promise.resolve(promise)
      .then((res) => {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        resolve(res);
      })
      .catch((err) => {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        reject(err);
      });
  });
}

function normalizeDraftAnswerList(rawList) {
  if (!Array.isArray(rawList)) return [];
  return rawList
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const questionId = safeText(item.questionId);
      const type = safeText(item.type);
      if (!questionId || !type) return null;
      return {
        questionId,
        type,
        selectedRadio: safeText(item.selectedRadio),
        selectedChecks: Array.isArray(item.selectedChecks)
          ? Array.from(
              new Set(
                item.selectedChecks
                  .map((value) => safeText(value))
                  .filter((value) => !!value)
              )
            ).sort()
          : [],
        fillValues: Array.isArray(item.fillValues)
          ? item.fillValues.map((value) => safeText(value))
          : [],
      };
    })
    .filter(Boolean);
}

function readDraftCache() {
  try {
    const payload = wx.getStorageSync(QUIZ_DRAFT_STORAGE_KEY);
    if (!payload || typeof payload !== "object") return null;
    const savedAt = Number(payload.savedAt) || 0;
    if (!savedAt || Date.now() - savedAt > QUIZ_DRAFT_MAX_AGE_MS) return null;
    const paperId = safeText(payload.paperId);
    const answers = normalizeDraftAnswerList(payload.answers);
    if (!paperId || !answers.length) return null;
    return {
      savedAt,
      paperId,
      currentIndex: Math.max(0, Number(payload.currentIndex) || 0),
      answers,
    };
  } catch (err) {
    return null;
  }
}

function clearDraftCache() {
  try {
    wx.removeStorageSync(QUIZ_DRAFT_STORAGE_KEY);
  } catch (err) {
    // ignore
  }
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

function restoreQuestionStateByDraft(question, draftAnswer) {
  if (!question || !draftAnswer) return question;
  if (question.type !== draftAnswer.type) return question;
  if (question.type === "radio") {
    const selectedRadio = safeText(draftAnswer.selectedRadio);
    if (!selectedRadio) return question;
    const hasOption = Array.isArray(question.options)
      ? question.options.some((item) => safeText(item && item.item) === selectedRadio)
      : false;
    if (!hasOption) return question;
    return {
      ...question,
      selectedRadio,
    };
  }

  if (question.type === "check") {
    const selectedChecks = Array.isArray(draftAnswer.selectedChecks)
      ? Array.from(new Set(draftAnswer.selectedChecks.map((value) => safeText(value)).filter(Boolean))).sort()
      : [];
    if (!selectedChecks.length) return question;
    const options = Array.isArray(question.options)
      ? question.options.map((option) => ({
          ...option,
          selected: selectedChecks.includes(safeText(option && option.item)),
        }))
      : [];
    return {
      ...question,
      options,
      selectedChecks,
    };
  }

  const inputValues = Array.isArray(draftAnswer.fillValues)
    ? draftAnswer.fillValues.map((value) => safeText(value))
    : [];
  const questionFillLen = Array.isArray(question.fillValues) ? question.fillValues.length : 0;
  const fillLen = Math.max(questionFillLen, inputValues.length, 1);
  const fillValues = [];
  for (let idx = 0; idx < fillLen; idx += 1) {
    fillValues.push(inputValues[idx] || "");
  }
  return {
    ...question,
    fillValues,
  };
}

function applyDraftToQuestions(questions, draft, paperId) {
  if (!Array.isArray(questions) || !questions.length) {
    return {
      questions: [],
      currentIndex: 0,
      restored: false,
    };
  }
  if (!draft || safeText(draft.paperId) !== safeText(paperId)) {
    return {
      questions,
      currentIndex: 0,
      restored: false,
    };
  }
  const answerMap = {};
  (draft.answers || []).forEach((item) => {
    if (!item || !item.questionId) return;
    answerMap[item.questionId] = item;
  });
  let restored = false;
  const nextQuestions = questions.map((question) => {
    const next = restoreQuestionStateByDraft(question, answerMap[question.questionId]);
    if (!restored && isQuestionAnswered(next)) restored = true;
    return next;
  });
  const maxIndex = Math.max(0, nextQuestions.length - 1);
  const currentIndex = Math.min(Math.max(0, Number(draft.currentIndex) || 0), maxIndex);
  return {
    questions: nextQuestions,
    currentIndex,
    restored,
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
    isRefreshingPaper: false,
    isSubmitting: false,
    hasStarted: false,
    errorMsg: "",
    loadedFromCache: false,
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
    draftRecovered: false,
    courseOptions: getQuizCourseOptions(),
    selectedCourseIndex: 1,
    selectedCourseLabel: "英语",
    durationOptions: QUIZ_DURATION_OPTIONS.map(formatDurationLabel),
    selectedDurationIndex: 1,
    selectedDurationLabel: formatDurationLabel(QUIZ_DURATION_OPTIONS[1]),
    remainingSeconds: 0,
    remainingText: "--:--",
  },

  onLoad() {
    const defaultCourse = "english";
    const courseOptions = getQuizCourseOptions();
    const selectedCourseIndex = Math.max(
      0,
      courseOptions.findIndex((item) => item.value === defaultCourse)
    );
    this.setData({
      courseOptions,
      selectedCourseIndex,
      selectedCourseLabel: getQuizCourseLabel(defaultCourse),
      durationOptions: QUIZ_DURATION_OPTIONS.map(formatDurationLabel),
      selectedDurationIndex: 1,
      selectedDurationLabel: formatDurationLabel(QUIZ_DURATION_OPTIONS[1]),
    });
  },

  onShow() {
    if (ensurePhase5Auth(QUIZ_TAB)) return;
    setTabBarSelected(this, QUIZ_TAB);
    this.syncCountdownDisplay({ triggerAutoSubmit: true });
    if (this.data.hasStarted && Number(this._quizDeadlineTs) > Date.now()) {
      this.clearCountdownTicker();
      this._countdownTicker = setInterval(() => {
        this.syncCountdownDisplay({ triggerAutoSubmit: true });
      }, 1000);
    }
    if (this.data.hasStarted && !this.data.paperId && !this.data.isLoading) {
      this.loadPaper({
        course: this.getSelectedCourse(),
      });
    }
  },

  onHide() {
    this.clearCountdownTicker();
  },

  onUnload() {
    this.clearCountdownTicker();
  },

  onPullDownRefresh() {
    if (!this.data.hasStarted) {
      wx.stopPullDownRefresh();
      wx.showToast({
        title: "请先点击开始测试",
        icon: "none",
      });
      return;
    }
    this.loadPaper({ manual: true, stopPullDown: true, course: this.data.paperCourse || this.getSelectedCourse() });
  },

  getSelectedCourse() {
    const options = Array.isArray(this.data.courseOptions) ? this.data.courseOptions : [];
    const item = options[this.data.selectedCourseIndex];
    return normalizeQuizCourse(item && item.value);
  },

  getSelectedDurationSeconds() {
    const idx = Math.max(0, Number(this.data.selectedDurationIndex) || 0);
    const minutes = QUIZ_DURATION_OPTIONS[idx] || QUIZ_DURATION_OPTIONS[0];
    return Math.max(60, Number(minutes) * 60);
  },

  clearCountdownTicker() {
    if (this._countdownTicker) {
      clearInterval(this._countdownTicker);
      this._countdownTicker = null;
    }
  },

  startCountdown(seconds) {
    const totalSeconds = Math.max(1, Number(seconds) || 1);
    this._quizDeadlineTs = Date.now() + totalSeconds * 1000;
    this.syncCountdownDisplay();
    this.clearCountdownTicker();
    this._countdownTicker = setInterval(() => {
      this.syncCountdownDisplay({ triggerAutoSubmit: true });
    }, 1000);
  },

  stopCountdown() {
    this.clearCountdownTicker();
    this._quizDeadlineTs = 0;
    this._isAutoSubmittingByTimeout = false;
    this.setData({
      remainingSeconds: 0,
      remainingText: "--:--",
    });
  },

  syncCountdownDisplay(options = {}) {
    const deadline = Number(this._quizDeadlineTs) || 0;
    if (!deadline) {
      if (this.data.remainingSeconds !== 0 || this.data.remainingText !== "--:--") {
        this.setData({
          remainingSeconds: 0,
          remainingText: "--:--",
        });
      }
      return;
    }

    const remain = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
    if (remain !== this.data.remainingSeconds || this.data.remainingText !== formatCountdown(remain)) {
      this.setData({
        remainingSeconds: remain,
        remainingText: formatCountdown(remain),
      });
    }

    if (remain <= 0) {
      this.stopCountdown();
      if (options.triggerAutoSubmit) {
        this.autoSubmitByTimeout();
      }
    }
  },

  autoSubmitByTimeout() {
    if (!this.data.hasStarted) return;
    if (this.data.isSubmitting || this._isAutoSubmittingByTimeout) return;
    this._isAutoSubmittingByTimeout = true;
    wx.showToast({
      title: "时间到，正在自动交卷",
      icon: "none",
    });
    this.submitQuiz({
      force: true,
      reason: "time_up",
    }).finally(() => {
      this._isAutoSubmittingByTimeout = false;
    });
  },

  clearPaperState() {
    this.setData({
      errorMsg: "",
      loadedFromCache: false,
      paperId: "",
      paperTitle: "",
      paperVersion: "",
      totalQuestions: 0,
      answeredQuestions: 0,
      unansweredQuestions: 0,
      progressPercent: 0,
      questions: [],
      currentIndex: 0,
      currentQuestion: null,
      submitToken: "",
      draftRecovered: false,
    });
  },

  handleCourseChange(event) {
    if (this.data.hasStarted) {
      wx.showToast({
        title: "测试进行中，不能切换科目",
        icon: "none",
      });
      return;
    }
    const nextIndex = Math.max(0, Number(event && event.detail && event.detail.value) || 0);
    const item = (this.data.courseOptions || [])[nextIndex] || {};
    const nextCourse = normalizeQuizCourse(item.value);
    this.setData({
      selectedCourseIndex: nextIndex,
      selectedCourseLabel: getQuizCourseLabel(nextCourse),
      paperCourse: nextCourse,
    });
    this.clearPaperState();
    clearDraftCache();
  },

  handleDurationChange(event) {
    if (this.data.hasStarted) {
      wx.showToast({
        title: "测试进行中，不能修改时长",
        icon: "none",
      });
      return;
    }
    const nextIndex = Math.max(0, Number(event && event.detail && event.detail.value) || 0);
    const minutes = QUIZ_DURATION_OPTIONS[nextIndex] || QUIZ_DURATION_OPTIONS[0];
    this.setData({
      selectedDurationIndex: nextIndex,
      selectedDurationLabel: formatDurationLabel(minutes),
    });
  },

  async handleStartQuiz() {
    if (this.data.isLoading || this.data.isSubmitting) return;
    if (this.data.hasStarted) {
      wx.showToast({
        title: "测试进行中",
        icon: "none",
      });
      return;
    }

    const targetCourse = this.getSelectedCourse();
    const durationSeconds = this.getSelectedDurationSeconds();
    this.clearPaperState();
    this.setData({
      hasStarted: true,
      paperCourse: targetCourse,
      selectedCourseLabel: getQuizCourseLabel(targetCourse),
    });
    this.startCountdown(durationSeconds);
    await this.loadPaper({
      manual: true,
      course: targetCourse,
    });
    if (!this.data.paperId || !this.data.questions.length) {
      this.setData({ hasStarted: false });
      this.stopCountdown();
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

  applyPaper(response, options = {}) {
    const questions = Array.isArray(response && response.questions) ? response.questions.map(normalizeQuestion) : [];
    const totalQuestions = Number(response && response.total_questions) || questions.length;
    const paperId = safeText(response && response.paper_id);
    const draft = readDraftCache();
    const restoredResult = applyDraftToQuestions(questions, draft, paperId);
    const normalizedCourse = normalizeQuizCourse(
      safeText(response && response.course) || options.course || this.getSelectedCourse()
    );

    this.setData({
      paperId,
      paperTitle: safeText(response && response.title) || `${getQuizCourseLabel(normalizedCourse)}伴学小测`,
      paperCourse: normalizedCourse,
      paperVersion: safeText(response && response.version),
      totalQuestions,
      draftRecovered: restoredResult.restored,
      selectedCourseLabel: getQuizCourseLabel(normalizedCourse),
    });
    this.syncQuestionState(restoredResult.questions, restoredResult.currentIndex, {
      clearToken: options.clearToken !== false,
    });
    if (restoredResult.restored && !options.silentRestoreNotice) {
      wx.showToast({
        title: "已恢复上次未完成作答",
        icon: "none",
      });
    }
    return restoredResult.restored;
  },

  async loadPaper(options = {}) {
    if (this.data.isLoading || this.data.isRefreshingPaper) return;
    const manual = !!options.manual;
    const stopPullDown = !!options.stopPullDown;
    const targetCourse = normalizeQuizCourse(options.course || this.data.paperCourse || this.getSelectedCourse());
    const hasQuestions = Array.isArray(this.data.questions) && this.data.questions.length > 0;
    const cachedPaper = readCachedPaper(targetCourse);
    let restoredByCachedPaper = false;

    if (!hasQuestions && cachedPaper) {
      restoredByCachedPaper = !!this.applyPaper(cachedPaper, {
        clearToken: true,
        course: targetCourse,
      });
      this.setData({
        loadedFromCache: true,
        errorMsg: "",
      });
    }

    const useBackgroundRefresh = hasQuestions || !!cachedPaper;
    this.setData({
      isLoading: !useBackgroundRefresh,
      isRefreshingPaper: useBackgroundRefresh,
      errorMsg: "",
      paperCourse: targetCourse,
    });
    try {
      const response = await getStudyQuizPaper(targetCourse);
      if (!isValidPaperPayload(response)) {
        throw new Error("试卷数据异常，请重试。");
      }
      writeCachedPaper(response, targetCourse);
      this.applyPaper(response, {
        clearToken: true,
        silentRestoreNotice: restoredByCachedPaper,
        course: targetCourse,
      });
      this.setData({
        loadedFromCache: false,
        errorMsg: "",
      });
      if (manual) {
        wx.showToast({
          title: "试卷已就绪",
          icon: "none",
        });
      }
    } catch (err) {
      const useCache = !!cachedPaper || hasQuestions;
      if (useCache) {
        this.setData({
          loadedFromCache: true,
          errorMsg: "",
        });
        if (manual) {
          wx.showToast({
            title: "网络波动，已用缓存题目",
            icon: "none",
          });
        }
      } else {
        const nextError = mapPaperLoadError(err);
        this.setData({
          errorMsg: nextError,
        });
      }
    } finally {
      this.setData({
        isLoading: false,
        isRefreshingPaper: false,
      });
      if (stopPullDown) {
        wx.stopPullDownRefresh();
      }
    }
  },

  handleRetryLoadPaper() {
    if (!this.data.hasStarted) {
      wx.showToast({
        title: "请先点击开始测试",
        icon: "none",
      });
      return;
    }
    this.loadPaper({
      manual: true,
      course: this.data.paperCourse || this.getSelectedCourse(),
    });
  },

  updateAnsweredCount(nextQuestions) {
    const currentIndex = this.data.currentIndex;
    this.syncQuestionState(nextQuestions, currentIndex, { clearToken: true });
    this.persistDraft(nextQuestions, currentIndex);
  },

  persistDraft(questions, currentIndex) {
    const paperId = safeText(this.data.paperId);
    const list = Array.isArray(questions) ? questions : [];
    if (!paperId || !list.length) return;
    const answers = list.map((item) => ({
      questionId: safeText(item && item.questionId),
      type: safeText(item && item.type),
      selectedRadio: safeText(item && item.selectedRadio),
      selectedChecks: Array.isArray(item && item.selectedChecks)
        ? Array.from(new Set(item.selectedChecks.map((value) => safeText(value)).filter(Boolean))).sort()
        : [],
      fillValues: Array.isArray(item && item.fillValues) ? item.fillValues.map((value) => safeText(value)) : [],
    }));
    try {
      wx.setStorageSync(QUIZ_DRAFT_STORAGE_KEY, {
        savedAt: Date.now(),
        paperId,
        currentIndex: Math.max(0, Number(currentIndex) || 0),
        answers,
      });
    } catch (err) {
      // ignore
    }
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
    this.persistDraft(this.data.questions, index);
  },

  handlePrevQuestion() {
    if (this.data.currentIndex <= 0) return;
    const nextIndex = this.data.currentIndex - 1;
    this.syncQuestionState(this.data.questions, nextIndex);
    this.persistDraft(this.data.questions, nextIndex);
  },

  handleNextQuestion() {
    const total = Number(this.data.totalQuestions) || (this.data.questions || []).length;
    if (this.data.currentIndex >= total - 1) return;
    const nextIndex = this.data.currentIndex + 1;
    this.syncQuestionState(this.data.questions, nextIndex);
    this.persistDraft(this.data.questions, nextIndex);
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
      course: this.data.paperCourse || this.getSelectedCourse(),
      paper_id: this.data.paperId || undefined,
      submit_token: submitToken || undefined,
      answers,
    };
  },

  async requestSubmitWithRetry(payload) {
    const totalAttempts = 2;
    let lastError = null;
    for (let attempt = 1; attempt <= totalAttempts; attempt += 1) {
      try {
        return await withClientTimeout(
          submitStudyQuiz(payload),
          attempt === 1 ? 15000 : 18000,
          "判分超时，请稍后重试。"
        );
      } catch (err) {
        lastError = err;
        const canRetry = isSubmitRetryableError(err) || safeText(err && err.message).includes("判分超时");
        if (!canRetry || attempt >= totalAttempts) break;
        wx.showToast({
          title: "网络波动，正在重试提交",
          icon: "none",
        });
      }
    }
    throw lastError || new Error("提交失败，请稍后重试。");
  },

  async submitQuiz(options = {}) {
    if (this.data.isSubmitting || this.data.isLoading) return;
    if (!this.data.hasStarted) {
      wx.showToast({
        title: "请先点击开始测试",
        icon: "none",
      });
      return;
    }

    const force = !!options.force;
    const submitReason = safeText(options.reason);

    if ((Number(this.data.answeredQuestions) || 0) <= 0 && !force) {
      const msg = "请先完成至少 1 题后再提交。";
      this.setData({ errorMsg: msg });
      wx.showToast({
        title: "请先作答",
        icon: "none",
      });
      return;
    }

    const unanswered = Number(this.data.unansweredQuestions) || 0;
    if (unanswered > 0 && !force) {
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
    wx.showLoading({ title: force ? "自动交卷中..." : "判分中..." });
    try {
      const response = await this.requestSubmitWithRetry(payload);
      const summary = (response && response.quiz_record) || {};
      const quizRecordId = safeText(summary.quiz_record_id);
      clearDraftCache();
      this.setData({
        draftRecovered: false,
        hasStarted: false,
      });
      this.stopCountdown();
      try {
        wx.setStorageSync(QUIZ_CONTEXT_STORAGE_KEY, response);
      } catch (err) {
        // ignore
      }
      wx.navigateTo({
        url: `/pages/study-quiz-result/index?quiz_record_id=${encodeURIComponent(quizRecordId)}&from=${encodeURIComponent(submitReason || "submit")}`,
      });
    } catch (err) {
      this.setData({
        errorMsg: mapSubmitError(err),
      });
    } finally {
      wx.hideLoading();
      this.setData({ isSubmitting: false });
    }
  },

  goAnalyzeDirectly() {
    wx.switchTab({ url: "/pages/analyze/index" });
  },

  openQuizBankIngestPage() {
    wx.navigateTo({
      url: `/pages/quiz-bank-ingest/index?course=${encodeURIComponent(this.getSelectedCourse())}`,
    });
  },
});
