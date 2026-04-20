const QUIZ_PAPER_CACHE_STORAGE_KEY = "ec_study_quiz_paper_cache_v1";
const QUIZ_PAPER_CACHE_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
const QUIZ_PAPER_PREFETCH_INTERVAL_MS = 20 * 60 * 1000;

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function isValidQuizPaperPayload(payload) {
  if (!payload || typeof payload !== "object") return false;
  if (!safeText(payload.paper_id)) return false;
  const questions = payload.questions;
  return Array.isArray(questions) && questions.length > 0;
}

function normalizeCourse(rawCourse) {
  const value = safeText(rawCourse).toLowerCase();
  return value || "english";
}

function normalizeCachePayload(raw) {
  if (!raw || typeof raw !== "object") {
    return {
      version: 2,
      entries: {},
    };
  }

  // Backward compatibility: old shape `{ savedAt, paper }`
  if (isValidQuizPaperPayload(raw.paper)) {
    const legacyCourse = normalizeCourse(raw.paper && raw.paper.course);
    return {
      version: 2,
      entries: {
        [legacyCourse]: {
          savedAt: Number(raw.savedAt) || Date.now(),
          paper: raw.paper,
        },
      },
    };
  }

  const entries = raw.entries && typeof raw.entries === "object" ? raw.entries : {};
  const nextEntries = {};
  Object.keys(entries).forEach((course) => {
    const key = normalizeCourse(course);
    const item = entries[course];
    if (!item || typeof item !== "object") return;
    if (!isValidQuizPaperPayload(item.paper)) return;
    nextEntries[key] = {
      savedAt: Number(item.savedAt) || Date.now(),
      paper: item.paper,
    };
  });
  return {
    version: 2,
    entries: nextEntries,
  };
}

function getQuizPaperCacheMeta(options = {}) {
  const targetCourse = normalizeCourse(options.course);
  try {
    const rawPayload = wx.getStorageSync(QUIZ_PAPER_CACHE_STORAGE_KEY);
    const payload = normalizeCachePayload(rawPayload);
    const entry = payload.entries[targetCourse];
    if (!entry || typeof entry !== "object") return null;
    const savedAt = Number(entry.savedAt) || 0;
    const paper = entry.paper;
    if (!savedAt || !isValidQuizPaperPayload(paper)) return null;
    const ageMs = Math.max(0, Date.now() - savedAt);
    return {
      course: targetCourse,
      savedAt,
      ageMs,
      expired: ageMs > QUIZ_PAPER_CACHE_MAX_AGE_MS,
      paper,
    };
  } catch (err) {
    return null;
  }
}

function readQuizPaperCache(options = {}) {
  const allowExpired = !!options.allowExpired;
  const meta = getQuizPaperCacheMeta({
    course: options.course,
  });
  if (!meta) return null;
  if (!allowExpired && meta.expired) return null;
  return meta.paper;
}

function writeQuizPaperCache(paper, options = {}) {
  if (!isValidQuizPaperPayload(paper)) return;
  const targetCourse = normalizeCourse(options.course || paper.course);
  try {
    const rawPayload = wx.getStorageSync(QUIZ_PAPER_CACHE_STORAGE_KEY);
    const payload = normalizeCachePayload(rawPayload);
    payload.entries[targetCourse] = {
      savedAt: Date.now(),
      paper,
    };
    wx.setStorageSync(QUIZ_PAPER_CACHE_STORAGE_KEY, {
      version: 2,
      entries: payload.entries,
    });
  } catch (err) {
    // ignore
  }
}

function shouldPrefetchQuizPaper(options = {}) {
  let course = "english";
  let minIntervalMs = QUIZ_PAPER_PREFETCH_INTERVAL_MS;
  if (typeof options === "number") {
    minIntervalMs = options;
  } else if (typeof options === "string") {
    course = options;
  } else if (options && typeof options === "object") {
    course = options.course || course;
    minIntervalMs = options.minIntervalMs || minIntervalMs;
  }
  const interval = Math.max(30 * 1000, Number(minIntervalMs) || QUIZ_PAPER_PREFETCH_INTERVAL_MS);
  const meta = getQuizPaperCacheMeta({ course });
  if (!meta) return true;
  if (meta.expired) return true;
  return meta.ageMs >= interval;
}

module.exports = {
  QUIZ_PAPER_CACHE_STORAGE_KEY,
  QUIZ_PAPER_CACHE_MAX_AGE_MS,
  QUIZ_PAPER_PREFETCH_INTERVAL_MS,
  isValidQuizPaperPayload,
  getQuizPaperCacheMeta,
  readQuizPaperCache,
  writeQuizPaperCache,
  shouldPrefetchQuizPaper,
};
