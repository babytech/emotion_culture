const { normalizeAssetUrl, sendEmail } = require("../../services/api");
const { uploadTempFile } = require("../../services/cloud");

function normalizeEmail(email) {
  return (email || "").trim();
}

function isEmailValid(email) {
  if (!email.includes("@")) return false;
  const domain = email.split("@")[1] || "";
  return domain.includes(".");
}

function pickRequest(context) {
  return (context && context.request) || {};
}

function pickResponse(context) {
  return (context && context.response) || {};
}

function pickUserImageFileId(req) {
  return req.imageFileId || req.image_file_id || req.userImageFileId || req.user_image_file_id || "";
}

function pickUserImageUrl(req) {
  return req.imageTempUrl || req.image_url || req.userImageUrl || req.user_image_url || "";
}

function pickUserImageTempPath(req) {
  return req.imageTempPath || req.image_temp_path || "";
}

Page({
  data: {
    hasData: false,
    emotionCode: "",
    emotionLabel: "",
    poet: "",
    poemText: "",
    interpretation: "",
    guochaoName: "",
    comfort: "",
    poetImageUrl: "",
    guochaoImageUrl: "",
    poetImageFailed: false,
    guochaoImageFailed: false,
    email: "",
    isSendingEmail: false,
    emailStatus: "",
  },

  onLoad() {
    const app = getApp();
    const context = app.globalData.latestAnalyzeContext;
    const response = pickResponse(context);

    if (!response || !response.emotion) {
      this.setData({ hasData: false });
      return;
    }

    this._analysisContext = context;

    this.setData({
      hasData: true,
      emotionCode: response.emotion.code || "",
      emotionLabel: response.emotion.label || "",
      poet: (response.poem && response.poem.poet) || "",
      poemText: (response.poem && response.poem.text) || "",
      interpretation: (response.poem && response.poem.interpretation) || "",
      guochaoName: (response.guochao && response.guochao.name) || "",
      comfort: (response.guochao && response.guochao.comfort) || "",
      poetImageUrl: normalizeAssetUrl(response.poet_image_url || ""),
      guochaoImageUrl: normalizeAssetUrl(response.guochao_image_url || ""),
      poetImageFailed: false,
      guochaoImageFailed: false,
    });
  },

  onPoetImageError() {
    this.setData({ poetImageFailed: true });
  },

  onGuochaoImageError() {
    this.setData({ guochaoImageFailed: true });
  },

  handleEmailInput(event) {
    this.setData({
      email: event.detail.value,
      emailStatus: "",
    });
  },

  async ensureUserImageRefs() {
    const context = this._analysisContext || {};
    const req = pickRequest(context);

    const existingFileId = pickUserImageFileId(req);
    const existingUrl = pickUserImageUrl(req);
    if (existingFileId || existingUrl) {
      return {
        fileId: existingFileId,
        tempUrl: existingUrl,
      };
    }

    const tempPath = pickUserImageTempPath(req);
    if (!tempPath) return { fileId: "", tempUrl: "" };

    wx.showLoading({ title: "补传图片中..." });
    try {
      const uploaded = await uploadTempFile(tempPath, "images");
      const fileId = (uploaded && uploaded.fileID) || "";
      const tempUrl = (uploaded && uploaded.tempFileURL) || "";
      if (!context.request) {
        context.request = {};
      }
      context.request.imageFileId = fileId;
      context.request.image_file_id = fileId;
      context.request.imageTempUrl = tempUrl;
      context.request.image_url = tempUrl;
      return {
        fileId,
        tempUrl,
      };
    } finally {
      wx.hideLoading();
    }
  },

  async submitEmail() {
    const toEmail = normalizeEmail(this.data.email);
    if (!toEmail) {
      wx.showToast({ title: "请输入邮箱地址", icon: "none" });
      return;
    }
    if (!isEmailValid(toEmail)) {
      wx.showToast({ title: "邮箱格式不正确", icon: "none" });
      return;
    }

    const context = this._analysisContext || {};
    const req = pickRequest(context);
    const resp = pickResponse(context);

    this.setData({
      isSendingEmail: true,
      emailStatus: "",
    });

    try {
      const userImageRefs = await this.ensureUserImageRefs();

      const payload = {
        to_email: toEmail,
        thoughts: req.text || "",
        poem_text: [this.data.poet, this.data.poemText, this.data.interpretation]
          .filter(Boolean)
          .join("\n"),
        comfort_text: [this.data.guochaoName, this.data.comfort]
          .filter(Boolean)
          .join("：\n"),
        user_image_url: userImageRefs.tempUrl || undefined,
        user_image_file_id: userImageRefs.fileId || undefined,
        poet_image_file_id: resp.poet_image_url || this.data.poetImageUrl || undefined,
        guochao_image_file_id: resp.guochao_image_url || this.data.guochaoImageUrl || undefined,
      };

      const result = await sendEmail(payload);
      this.setData({
        emailStatus: result.message || "邮件发送完成",
      });
      wx.showToast({
        title: result.success ? "发送成功" : "发送失败",
        icon: "none",
      });
    } catch (err) {
      this.setData({
        emailStatus: err.message || "邮件发送失败",
      });
      wx.showToast({
        title: "发送失败",
        icon: "none",
      });
    } finally {
      this.setData({ isSendingEmail: false });
    }
  },

  backHome() {
    wx.navigateBack({
      delta: 1,
      fail() {
        wx.reLaunch({ url: "/pages/index/index" });
      },
    });
  },
});
