module.exports = {
  // Optional: used for loading `/assets/...` image URLs in result pages.
  // Keep this as your cloud hosting domain if you need backend static images.
  apiBaseUrl: "https://emotion-culture-api-237560-9-1415063583.sh.run.tcloudbase.com",

  // WeChat Cloud Development env id (used by wx.cloud.uploadFile and cloud init).
  // cloudEnv: "emotion-culture-cloud-dev-952b26",
  cloudEnv: "prod-9gok8bmyd517976f",

  // Cloud Hosting env id for wx.cloud.callContainer.
  // If your container service is deployed under a different env than `cloudEnv`, set it here.
  containerEnv: "prod-9gok8bmyd517976f",

  // Cloud Hosting service name for wx.cloud.callContainer.
  containerService: "emotion-culture-api",

  // Identity strategy:
  // - default: rely on WeChat natural identity injected by Cloud Hosting headers (x-wx-openid)
  // - fallback: set true only for local/dev environments that cannot provide WeChat identity
  enableClientUserIdFallback: false,

  // Optional admin token for quiz bank ingest endpoint.
  // Keep empty unless backend configured STUDY_QUIZ_ADMIN_TOKEN.
  studyQuizAdminToken: "",
};
