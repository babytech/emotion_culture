const { normalizeAssetUrl, sendEmail } = require("../../services/api");
const { uploadTempFile } = require("../../services/cloud");

function normalizeEmail(email) {
  return (email || "").trim();
}

function getEmailError(email) {
  if (!email) return "";
  if (email.length > 320) return "邮箱长度不能超过 320 个字符";
  const basicPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
  if (!basicPattern.test(email)) return "邮箱地址格式有误，请检查后重试";
  return "";
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
    emailError: "",
    emailFocused: false,
    keyboardHeight: 0,
    bottomPaddingPx: 0,
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

    if (wx.onKeyboardHeightChange) {
      this._keyboardHandler = (res) => {
        const height = Math.max(0, (res && res.height) || 0);
        this.setData(
          {
            keyboardHeight: height,
            bottomPaddingPx: height > 0 ? height + 24 : 0,
          },
          () => {
            if (height > 0) this.scrollToEmailSection();
          }
        );
      };
      wx.onKeyboardHeightChange(this._keyboardHandler);
    }
  },

  onUnload() {
    if (this._keyboardHandler && wx.offKeyboardHeightChange) {
      wx.offKeyboardHeightChange(this._keyboardHandler);
    }
  },

  scrollToEmailSection() {
    wx.pageScrollTo({
      selector: "#email-section",
      duration: 120,
      offsetTop: 60,
      fail() {
        // ignore
      },
    });
  },

  handleEmailFocus() {
    this.setData({ emailFocused: true });
    this.scrollToEmailSection();
  },

  handleEmailBlur() {
    const normalized = normalizeEmail(this.data.email);
    this.setData({
      emailFocused: false,
      emailError: getEmailError(normalized),
    });
  },

  onPoetImageError() {
    this.setData({ poetImageFailed: true });
  },

  onGuochaoImageError() {
    this.setData({ guochaoImageFailed: true });
  },

  handleEmailInput(event) {
    const raw = (event && event.detail && event.detail.value) || "";
    const normalized = normalizeEmail(raw);
    this.setData({
      email: raw,
      emailError: getEmailError(normalized),
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
    const emailError = !toEmail ? "请输入邮箱地址" : getEmailError(toEmail);
    if (emailError) {
      this.setData({ emailError });
      this.scrollToEmailSection();
      wx.showToast({ title: emailError, icon: "none" });
      return;
    }

    this.setData({
      email: toEmail,
      emailError: "",
    });

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
