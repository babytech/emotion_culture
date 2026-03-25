const { analyze } = require("../../services/api");
const { uploadTempFile } = require("../../services/cloud");

const recorder = wx.getRecorderManager();
const IMAGE_COMPRESS_SKIP_BYTES = 900 * 1024;
const IMAGE_COMPRESS_MEDIUM_BYTES = 2 * 1024 * 1024;
const IMAGE_COMPRESS_HEAVY_BYTES = 4 * 1024 * 1024;

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

Page({
  data: {
    text: "",
    imageTempPath: "",
    audioTempPath: "",
    isRecording: false,
    recordSeconds: 0,
    isSubmitting: false,
    errorMsg: "",
  },

  onLoad() {
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
      errorMsg: "",
    });
  },

  async chooseImage() {
    try {
      const res = await wx.chooseImage({
        count: 1,
        sizeType: ["compressed"],
        sourceType: ["camera", "album"],
      });

      const tempPath =
        (res.tempFilePaths && res.tempFilePaths[0]) ||
        (res.tempFiles && res.tempFiles[0] && res.tempFiles[0].path) ||
        "";
      if (!tempPath) {
        throw new Error("未获取到图片");
      }

      this.setData({
        imageTempPath: tempPath,
        errorMsg: "",
      });
    } catch (err) {
      if ((err.errMsg || "").includes("cancel")) return;
      wx.showToast({
        title: err.message || "选择图片失败",
        icon: "none",
      });
    }
  },

  clearImage() {
    this.setData({ imageTempPath: "" });
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
    });
  },

  async submitAnalyze() {
    const text = (this.data.text || "").trim();
    const imageTempPath = this.data.imageTempPath;
    const audioTempPath = this.data.audioTempPath;

    if (!text && !imageTempPath && !audioTempPath) {
      this.setData({ errorMsg: "请至少提供文本、图片或语音中的一种输入。" });
      return;
    }

    this.setData({
      isSubmitting: true,
      errorMsg: "",
    });

    try {
      let imageFileId = "";
      let imageTempUrl = "";
      let audioFileId = "";
      let audioTempUrl = "";

      if (imageTempPath) {
        wx.showLoading({ title: "上传图片中..." });
        const preparedImage = await prepareImageForUpload(imageTempPath);
        const uploadedImage = await uploadTempFile(preparedImage.path, "images");
        imageFileId = (uploadedImage && uploadedImage.fileID) || "";
        imageTempUrl = (uploadedImage && uploadedImage.tempFileURL) || "";
      }

      if (audioTempPath) {
        wx.showLoading({ title: "上传语音中..." });
        const uploadedAudio = await uploadTempFile(audioTempPath, "audio");
        audioFileId = (uploadedAudio && uploadedAudio.fileID) || "";
        audioTempUrl = (uploadedAudio && uploadedAudio.tempFileURL) || "";
      }

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

      wx.navigateTo({
        url: "/pages/result/result",
      });
    } catch (err) {
      this.setData({
        errorMsg: err.message || "分析失败，请稍后重试。",
      });
      wx.showToast({
        title: "分析失败",
        icon: "none",
      });
    } finally {
      wx.hideLoading();
      this.setData({ isSubmitting: false });
    }
  },
});
