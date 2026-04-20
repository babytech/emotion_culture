const QUIZ_COURSE_OPTIONS = [
  { value: "chinese", label: "语文" },
  { value: "english", label: "英语" },
  { value: "math", label: "数学" },
  { value: "physics", label: "物理" },
  { value: "chemistry", label: "化学" },
  { value: "history", label: "历史" },
  { value: "geography", label: "地理" },
];

const QUIZ_COURSE_LABEL_MAP = QUIZ_COURSE_OPTIONS.reduce((acc, item) => {
  if (!item || !item.value) return acc;
  acc[item.value] = item.label;
  return acc;
}, {});

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function normalizeQuizCourse(rawCourse, fallback = "english") {
  const normalized = safeText(rawCourse).toLowerCase();
  if (!normalized) return fallback;
  if (QUIZ_COURSE_LABEL_MAP[normalized]) return normalized;
  return fallback;
}

function getQuizCourseLabel(rawCourse) {
  const normalized = normalizeQuizCourse(rawCourse, "");
  if (!normalized) return "课程";
  return QUIZ_COURSE_LABEL_MAP[normalized] || "课程";
}

function getQuizCourseOptions() {
  return QUIZ_COURSE_OPTIONS.map((item) => ({ ...item }));
}

module.exports = {
  QUIZ_COURSE_OPTIONS,
  getQuizCourseOptions,
  getQuizCourseLabel,
  normalizeQuizCourse,
};
