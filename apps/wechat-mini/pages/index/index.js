const { analyze } = require("../../services/api");
const { uploadTempFile } = require("../../services/cloud");

const recorder = wx.getRecorderManager();
const IMAGE_COMPRESS_SKIP_BYTES = 900 * 1024;
const IMAGE_COMPRESS_MEDIUM_BYTES = 2 * 1024 * 1024;
const IMAGE_COMPRESS_HEAVY_BYTES = 4 * 1024 * 1024;
const SUBMIT_STAGE = {
  IDLE: "idle",
  UPLOADING: "uploading",
  ANALYZING: "analyzing",
  RENDERING: "rendering",
  FAILED: "failed",
};

function getFileSize(path) {
  return new Promise((resolve) => {
    try {
      wx.getFileSystemManager().stat({
        path,
        success(res) {
          resolve((res.stats && res.stats.size) || 0);
        },
        fail() {
          resolve(0);
        },
      });
    } catch (err) {
      resolve(0);
    }
  });
}

function compressImage(path, quality) {
  return new Promise((resolve, reject) => {
    wx.compressImage({
      src: path,
      quality,
      success(res) {
        resolve((res && res.tempFilePath) || path);
      },
      fail(err) {
        reject(err);
      },
    });
  });
}

function extractTempImagePath(res) {
  return (
    (res &&
      res.tempFiles &&
      res.tempFiles[0] &&
      (res.tempFiles[0].tempFilePath || res.tempFiles[0].path)) ||
    (res && res.tempFilePaths && res.tempFilePaths[0]) ||
    ""
  );
}

async function prepareImageForUpload(path) {
  const sizeBefore = await getFileSize(path);
  if (sizeBefore > 0 && sizeBefore <= IMAGE_COMPRESS_SKIP_BYTES) {
    return { path, compressed: false, sizeBefore, sizeAfter: sizeBefore };
  }

  let quality = 82;
  if (sizeBefore >= IMAGE_COMPRESS_HEAVY_BYTES) quality = 68;
  else if (sizeBefore >= IMAGE_COMPRESS_MEDIUM_BYTES) quality = 76;

  try {
    const compressedPath = await compressImage(path, quality);
    const sizeAfter = await getFileSize(compressedPath);
    if (!sizeAfter || (sizeBefore > 0 && sizeAfter >= sizeBefore)) {
      return { path, compressed: false, sizeBefore, sizeAfter: sizeBefore };
    }
    return { path: compressedPath, compressed: compressedPath !== path, sizeBefore, sizeAfter };
  } catch (err) {
    console.warn("compressImage failed, fallback to original", err);
    return { path, compressed: false, sizeBefore, sizeAfter: sizeBefore };
  }
}

function buildRecoverableAnalyzeError(err) {
  const message = ((err && err.message) || "分析失败，请稍后重试。").trim();
  if (!message) {
    return "分析失败，请重试。你之前填写的内容已保留。";
  }

  if (message.includes("[VOICE_")) {
    return `${message} 可重新录音，或改用文字输入后再次提交。`;
  }
  if (message.includes("[FACE_")) {
    return `${message} 可重新自拍后再次提交。`;
  }
  return `${message} 可直接重试，原输入已保留。`;
}

Page({
  data: {
    text: "",
    imageTempPath: "",
    pendingSelfiePath: "",
    audioTempPath: "",
    isRecording: false,
    recordSeconds: 0,
    isSubmitting: false,
    submitStage: SUBMIT_STAGE.IDLE,
    submitStatusText: "",
    submitButtonText: "提交分析",
    errorMsg: "",
    isDevtools: false,
  },

  onLoad() {
    let isDevtools = false;
    try {
      const sysInfo = wx.getSystemInfoSync();
      isDevtools = !!sysInfo && sysInfo.platform === "devtools";
    } catch (err) {
      isDevtools = false;
    }
    this.setData({ isDevtools });
    this.bindRecorderEvents();
  },

  onUnload() {
    this.stopRecordTimer();
    if (this.data.isRecording) {
      try {
        recorder.stop();
      } catch (e) {
        // ignore
      }
    }
  },

  bindRecorderEvents() {
    if (this._recorderBound) return;
    this._recorderBound = true;

    recorder.onStart(() => {
      this.setData({
        isRecording: true,
        recordSeconds: 0,
      });
      this.startRecordTimer();
    });

    recorder.onStop((res) => {
      this.stopRecordTimer();
      this.setData({
        isRecording: false,
        audioTempPath: res.tempFilePath || "",
      });
    });

    recorder.onError((err) => {
      this.stopRecordTimer();
      this.setData({ isRecording: false });
      wx.showToast({
        title: err.errMsg || "录音失败",
        icon: "none",
      });
    });
  },

  startRecordTimer() {
    this.stopRecordTimer();
    this._recordTimer = setInterval(() => {
      this.setData({
        recordSeconds: this.data.recordSeconds + 1,
      });
    }, 1000);
  },

  stopRecordTimer() {
    if (this._recordTimer) {
      clearInterval(this._recordTimer);
      this._recordTimer = null;
    }
  },

  handleTextInput(event) {
    this.setData({
      text: event.detail.value,
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  async chooseSelfie() {
    let tempPath = "";
    try {
      const mediaRes = await wx.chooseMedia({
        count: 1,
        mediaType: ["image"],
        sizeType: ["original"],
        sourceType: ["camera"],
        camera: "front",
      });
      tempPath = extractTempImagePath(mediaRes);
    } catch (err) {
      const message = (err && err.errMsg) || "";
      if (!message.includes("cancel")) {
        try {
          const imageRes = await wx.chooseImage({
            count: 1,
            sizeType: ["original"],
            sourceType: ["camera"],
          });
          tempPath = extractTempImagePath(imageRes);
        } catch (fallbackErr) {
          if ((fallbackErr.errMsg || "").includes("cancel")) return;
          wx.showToast({
            title: fallbackErr.message || "拍照失败",
            icon: "none",
          });
          return;
        }
      } else {
        return;
      }
    }

    if (!tempPath) {
      wx.showToast({
        title: "未获取到自拍照片",
        icon: "none",
      });
      return;
    }

    this.setData({
      imageTempPath: "",
      pendingSelfiePath: tempPath,
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  confirmSelfie() {
    if (!this.data.pendingSelfiePath) return;
    this.setData({
      imageTempPath: this.data.pendingSelfiePath,
      pendingSelfiePath: "",
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  async retakeSelfie() {
    this.setData({
      imageTempPath: "",
      pendingSelfiePath: "",
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
    await this.chooseSelfie();
  },

  cancelPendingSelfie() {
    this.setData({
      pendingSelfiePath: "",
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
      errorMsg: "",
    });
  },

  clearImage() {
    this.setData({
      imageTempPath: "",
      pendingSelfiePath: "",
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
    });
  },

  startRecord() {
    if (this.data.isRecording) return;

    recorder.start({
      duration: 60000,
      sampleRate: 16000,
      numberOfChannels: 1,
      encodeBitRate: 96000,
      format: "mp3",
      frameSize: 50,
    });
  },

  stopRecord() {
    if (!this.data.isRecording) return;
    recorder.stop();
  },

  clearAudio() {
    this.setData({
      audioTempPath: "",
      recordSeconds: 0,
      submitStage: SUBMIT_STAGE.IDLE,
      submitStatusText: "",
      submitButtonText: "提交分析",
    });
  },

  goHistory() {
    wx.navigateTo({ url: "/pages/history/index" });
  },

  goSettings() {
    wx.navigateTo({ url: "/pages/settings/index" });
  },

  async submitAnalyze() {
    const text = (this.data.text || "").trim();
    const imageTempPath = this.data.imageTempPath;
    const pendingSelfiePath = this.data.pendingSelfiePath;
    const audioTempPath = this.data.audioTempPath;

    if (pendingSelfiePath && !imageTempPath) {
      this.setData({ errorMsg: "请先确认自拍照片，再提交分析。" });
      return;
    }

    if (!text && !imageTempPath && !audioTempPath) {
      this.setData({ errorMsg: "请至少提供文本、自拍或语音中的一种输入。" });
      return;
    }

    this.setData({
      isSubmitting: true,
      submitStage: SUBMIT_STAGE.UPLOADING,
      submitStatusText: "上传中：正在准备输入内容...",
      submitButtonText: "上传中...",
      errorMsg: "",
    });

    let submitSucceeded = false;
    try {
      let imageFileId = "";
      let imageTempUrl = "";
      let audioFileId = "";
      let audioTempUrl = "";

      if (imageTempPath) {
        this.setData({
          submitStage: SUBMIT_STAGE.UPLOADING,
          submitStatusText: "上传中：正在上传自拍照片...",
        });
        wx.showLoading({ title: "上传图片中..." });
        const preparedImage = await prepareImageForUpload(imageTempPath);
        const uploadedImage = await uploadTempFile(preparedImage.path, "images");
        imageFileId = (uploadedImage && uploadedImage.fileID) || "";
        imageTempUrl = (uploadedImage && uploadedImage.tempFileURL) || "";
      }

      if (audioTempPath) {
        this.setData({
          submitStage: SUBMIT_STAGE.UPLOADING,
          submitStatusText: "上传中：正在上传语音...",
        });
        wx.showLoading({ title: "上传语音中..." });
        const uploadedAudio = await uploadTempFile(audioTempPath, "audio");
        audioFileId = (uploadedAudio && uploadedAudio.fileID) || "";
        audioTempUrl = (uploadedAudio && uploadedAudio.tempFileURL) || "";
      }

      this.setData({
        submitStage: SUBMIT_STAGE.ANALYZING,
        submitStatusText: "分析中：正在生成情绪结果...",
        submitButtonText: "分析中...",
      });
      wx.showLoading({ title: "分析中..." });

      const inputModes = [];
      if (text) inputModes.push("text");
      if (imageTempUrl || imageFileId) inputModes.push("selfie");
      if (audioTempUrl || audioFileId) inputModes.push("voice");

      const result = await analyze({
        input_modes: inputModes,
        text: text || undefined,
        image:
          imageTempUrl || imageFileId
            ? {
                url: imageTempUrl || undefined,
                file_id: imageFileId || undefined,
              }
            : undefined,
        audio:
          audioTempUrl || audioFileId
            ? {
                url: audioTempUrl || undefined,
                file_id: audioFileId || undefined,
              }
            : undefined,

        // Legacy fields kept until all clients migrate.
        image_url: imageTempUrl || undefined,
        image_file_id: imageFileId || undefined,
        audio_url: audioTempUrl || undefined,
        audio_file_id: audioFileId || undefined,
        client: {
          platform: "mp-weixin",
          version: "0.1.0",
        },
      });

      this.setData({
        submitStage: SUBMIT_STAGE.RENDERING,
        submitStatusText: "结果生成中：正在打开结果页...",
        submitButtonText: "结果生成中...",
      });
      wx.showLoading({ title: "结果生成中..." });

      const app = getApp();
      app.globalData.latestAnalyzeContext = {
        request: {
          text,
          input_modes: inputModes,
          image:
            imageTempUrl || imageFileId
              ? { url: imageTempUrl, file_id: imageFileId }
              : undefined,
          audio:
            audioTempUrl || audioFileId
              ? { url: audioTempUrl, file_id: audioFileId }
              : undefined,
          imageFileId,
          imageTempUrl,
          audioFileId,
          audioTempUrl,
          imageTempPath,
          audioTempPath,
          image_url: imageTempUrl,
          image_file_id: imageFileId,
          audio_url: audioTempUrl,
          audio_file_id: audioFileId,
          image_temp_path: imageTempPath,
          audio_temp_path: audioTempPath,
        },
        response: result,
      };

      submitSucceeded = true;
      wx.navigateTo({
        url: "/pages/result/result",
      });
    } catch (err) {
      const errorMsg = buildRecoverableAnalyzeError(err);
      this.setData({
        submitStage: SUBMIT_STAGE.FAILED,
        submitStatusText: "分析失败：可直接重试，原输入已保留。",
        submitButtonText: "提交分析",
        errorMsg,
      });
      wx.showToast({
        title: "分析失败，可重试",
        icon: "none",
      });
    } finally {
      wx.hideLoading();
      this.setData({
        isSubmitting: false,
        submitStage: submitSucceeded ? SUBMIT_STAGE.IDLE : this.data.submitStage,
        submitStatusText: submitSucceeded ? "" : this.data.submitStatusText,
        submitButtonText: "提交分析",
      });
    }
  },
});
