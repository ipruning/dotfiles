// settings
settings.digitForRepeat = false;
settings.focusAfterClosed = "right";
settings.focusFirstCandidate = true;
settings.tabsThreshold = 0;

api.Hints.style(`
  font-family: SF Mono, monospace;
`);
settings.theme = `
.sk_theme #sk_omnibarSearchArea input, #sk_omnibarSearchResult {
  font-size: 14px;
}
`;

// Search engine configuration
const SEARCH_ENGINE = "https://kagi.com/search?q=";
api.addSearchAlias("k", "kagi", SEARCH_ENGINE, "s");
settings.defaultSearchEngine = "k";

// Scrolling controls
api.mapkey("<Ctrl-d>", "Scroll down half page", () => api.Normal.scroll("pageDown"));
api.mapkey("<Ctrl-u>", "Scroll up half page", () => api.Normal.scroll("pageUp"));

// URL and clipboard operations
api.mapkey("ym", "Copy current page URL as Markdown link", () =>
  api.Clipboard.write(`[${document.title}](${window.location.href})`),
);

// URL validation pattern
// Matches: domain.com, sub.domain.com, http(s)://domain.com, with optional path
const URL_PATTERN = /^(https?:\/\/)?([\da-z.-]+)\.([a-z.]{2,6})([/\w .-]*)*\/?$/;

// Error handling for clipboard operations
function handleClipboardError(error) {
  api.Front.showBanner(`Failed to access clipboard: ${error.message}`, 3000);
}

/**
 * Process clipboard text and open as URL or search
 * @param {string} clipText - Text from clipboard
 * @param {boolean} openInNewTab - Whether to open in new tab
 */
function processClipboardText(clipText, openInNewTab = false) {
  try {
    const markInfo = {
      scrollLeft: 0,
      scrollTop: 0,
      tab: {
        tabbed: openInNewTab,
        active: openInNewTab,
      },
    };

    // If text is a valid URL, open it directly (adding https:// if needed)
    // Otherwise, use it as a search query
    if (URL_PATTERN.test(clipText)) {
      markInfo.url = clipText.startsWith("http") ? clipText : `https://${clipText}`;
    } else {
      markInfo.url = `${SEARCH_ENGINE}${encodeURIComponent(clipText)}`;
    }

    api.RUNTIME("openLink", markInfo);
  } catch (error) {
    handleClipboardError(error);
  }
}

// Clipboard URL opening mappings
api.mapkey("go", "Open URL in clipboard", () =>
  api.Clipboard.read((response) => {
    if (response?.data) {
      processClipboardText(response.data.trim(), false);
    } else {
      handleClipboardError(new Error("No content in clipboard"));
    }
  }),
);

api.mapkey("gO", "Open URL in clipboard in new tab", () =>
  api.Clipboard.read((response) => {
    if (response?.data) {
      processClipboardText(response.data.trim(), true);
    } else {
      handleClipboardError(new Error("No content in clipboard"));
    }
  }),
);

// Timeout durations for PassThrough mode
const TIMEOUT_SHORT_MS = 1500;
const TIMEOUT_LONG_MS = 300000;

api.mapkey("p", "Enter PassThrough mode", () => {
  const seconds = TIMEOUT_SHORT_MS / 1000;
  api.Front.showBanner(`Entering PassThrough mode for ${seconds}s, press ESC to exit early`, 1600);
  api.Normal.passThrough(TIMEOUT_SHORT_MS);
});

api.mapkey("P", "Enter PassThrough mode", () => {
  const seconds = TIMEOUT_LONG_MS / 1000;
  api.Front.showBanner(`Entering PassThrough mode for ${seconds}s, press ESC to exit early`, 1600);
  api.Normal.passThrough(TIMEOUT_LONG_MS);
});

const UNMAP_ALL_DOMAINS_REGEX = /\b(feishu\.cn|monkeytype\.com|notion\.so|roamresearch\.com)\b/i;

api.unmapAllExcept(
  [
    // Scrolling
    "<Ctrl-d>",
    "<Ctrl-u>",
    "e",
    "d",
    // Navigation
    "E",
    "R",
    "B",
    "F",
    // Tabs
    "S",
    "D",
    "x",
    "X",
    // Misc
    ";",
    "t",
    "T",
    "i",
    "p",
    "P",
  ],
  UNMAP_ALL_DOMAINS_REGEX,
);

api.unmap("?", /\b(kagi\.com)\b/i);
api.unmap("h", /\b(kagi\.com)\b/i); // Navigation
api.unmap("j", /\b(kagi\.com)\b/i); // Navigation
api.unmap("k", /\b(kagi\.com)\b/i); // Navigation
api.unmap("l", /\b(kagi\.com)\b/i); // Navigation
api.unmap("/", /\b(kagi\.com)\b/i); // Search
api.unmap("q", /\b(kagi\.com)\b/i); // Open quick answer
api.unmap("s", /\b(kagi\.com)\b/i); // Open site info modal on the currently highlighted result if applicable, or close it if already open

api.unmap("?", /\b(x\.com)\b/i);
api.unmap("j", /\b(x\.com)\b/i); // Navigation
api.unmap("k", /\b(x\.com)\b/i); // Navigation
api.unmap("g", /\b(x\.com)\b/i); // Navigation 
api.unmap("/", /\b(x\.com)\b/i); // Search
api.unmap(".", /\b(x\.com)\b/i); // Refresh
api.unmap("n", /\b(x\.com)\b/i); // New post
api.unmap("m", /\b(x\.com)\b/i); // New direct message
api.unmap("l", /\b(x\.com)\b/i); // Like
api.unmap("r", /\b(x\.com)\b/i); // Reply
api.unmap("s", /\b(x\.com)\b/i); // Share post
api.unmap("u", /\b(x\.com)\b/i); // Mute account

api.unmap("?", /\b(github\.com)\b/i);
api.unmap("/", /\b(github\.com)\b/i); // Search

api.unmap("r", /\b(roamresearch\.com)\b/i);
api.unmap("esc", /\b(roamresearch\.com)\b/i);
