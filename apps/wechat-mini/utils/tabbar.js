const HOME_TAB = "/pages/home/index";
const QUIZ_TAB = "/pages/study-quiz/index";
const QUIZ_RESULT_TAB = "/pages/study-quiz-result/index";
const JOURNEY_TAB = "/pages/journey/index";
const ANALYZE_TAB = "/pages/analyze/index";
const FAVORITES_TAB = "/pages/favorites/index";
const PROFILE_TAB = "/pages/profile/index";
const VISIBLE_TABS = new Set([HOME_TAB, QUIZ_TAB, ANALYZE_TAB, JOURNEY_TAB, PROFILE_TAB]);

function setTabBarSelected(page, selected) {
  if (!page || typeof page.getTabBar !== "function") return;

  const tabBar = page.getTabBar();
  if (!tabBar || typeof tabBar.setData !== "function") return;

  tabBar.setData({
    selected: VISIBLE_TABS.has(selected) ? selected : "",
  });
}

module.exports = {
  HOME_TAB,
  QUIZ_TAB,
  QUIZ_RESULT_TAB,
  JOURNEY_TAB,
  ANALYZE_TAB,
  FAVORITES_TAB,
  PROFILE_TAB,
  setTabBarSelected,
};
