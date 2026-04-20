const { ingestStudyQuizBankFile } = require("../../services/api");
const { getQuizCourseLabel, getQuizCourseOptions, normalizeQuizCourse } = require("../../utils/study-quiz-course");

function safeText(value) {
  return typeof value === "string" ? value.trim() : "";
}

function parseErrorMessage(err) {
  const text = safeText(err && err.message);
  if (!text) return "上传失败，请稍后重试。";
  if (text.length > 120) return "上传失败，请稍后重试。";
  return text;
}

Page({
  data: {
    courseOptions: getQuizCourseOptions(),
    selectedCourseIndex: 1,
    selectedCourseLabel: "英语",
    isUploading: false,
    uploadHint: "支持拍照录入题目（jpg/png/pdf）。",
    latestResultText: "",
  },

  onLoad(options) {
    const defaultCourse = normalizeQuizCourse(options && decodeURIComponent(options.course || ""), "english");
    const optionsList = getQuizCourseOptions();
    const selectedCourseIndex = Math.max(
      0,
      optionsList.findIndex((item) => item.value === defaultCourse)
    );
    this.setData({
      courseOptions: optionsList,
      selectedCourseIndex,
      selectedCourseLabel: getQuizCourseLabel(defaultCourse),
    });
  },

  getSelectedCourse() {
    const list = Array.isArray(this.data.courseOptions) ? this.data.courseOptions : [];
    const item = list[this.data.selectedCourseIndex];
    return normalizeQuizCourse(item && item.value, "english");
  },

  handleCourseChange(event) {
    const nextIndex = Math.max(0, Number(event && event.detail && event.detail.value) || 0);
    const nextCourse = normalizeQuizCourse(
      (this.data.courseOptions[nextIndex] && this.data.courseOptions[nextIndex].value) || "english",
      "english"
    );
    this.setData({
      selectedCourseIndex: nextIndex,
      selectedCourseLabel: getQuizCourseLabel(nextCourse),
    });
  },

  async handleCaptureAndIngest() {
    if (this.data.isUploading) return;
    const course = this.getSelectedCourse();
    const courseLabel = getQuizCourseLabel(course);

    let chooseResult = null;
    try {
      chooseResult = await new Promise((resolve, reject) => {
        wx.chooseMedia({
          count: 1,
          mediaType: ["image"],
          sourceType: ["camera"],
          camera: "back",
          sizeType: ["compressed"],
          success: resolve,
          fail: reject,
        });
      });
    } catch (err) {
      wx.showToast({
        title: "未完成拍照",
        icon: "none",
      });
      return;
    }

    const file = (chooseResult && chooseResult.tempFiles && chooseResult.tempFiles[0]) || {};
    const tempFilePath = safeText(file.tempFilePath);
    if (!tempFilePath) {
      wx.showToast({
        title: "未获取到拍照文件",
        icon: "none",
      });
      return;
    }

    this.setData({
      isUploading: true,
      uploadHint: "识别中，请稍候...",
      latestResultText: "",
    });
    wx.showLoading({
      title: "题库识别中...",
    });

    try {
      const response = await ingestStudyQuizBankFile({
        tempFilePath,
        course,
        title: `${courseLabel}伴学小测`,
      });
      const totalQuestions = Math.max(0, Number(response && response.total_questions) || 0);
      const version = safeText(response && response.version);
      const versionLabel = version ? `，版本 ${version}` : "";
      const resultText = `${courseLabel}题库已更新，共 ${totalQuestions} 题${versionLabel}`;
      this.setData({
        latestResultText: resultText,
        uploadHint: "录入成功，可返回测试页开始测试。",
      });
      wx.showToast({
        title: "录入成功",
        icon: "success",
      });
    } catch (err) {
      const message = parseErrorMessage(err);
      this.setData({
        uploadHint: message,
      });
      wx.showToast({
        title: message,
        icon: "none",
      });
    } finally {
      wx.hideLoading();
      this.setData({
        isUploading: false,
      });
    }
  },
});
