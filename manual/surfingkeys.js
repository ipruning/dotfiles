// settings
settings.digitForRepeat = false;
settings.focusAfterClosed = "right";
settings.focusFirstCandidate = true;
settings.tabsThreshold = 0;
settings.blocklistPattern = /^https?:\/\/jetkvm\.mastodon-beta\.ts\.net(?::\d+)?(?:[/?#]|$)/i;

function siteUrlPattern(domains) {
  const alternatives = domains.map((domain) => domain.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  return new RegExp(`^https?://(?:[^./:?#]+\\.)*(?:${alternatives})(?::\\d+)?(?:[/?#]|$)`, "i");
}

api.Hints.style(`
  font-family: MonoLisaCode;
  font-size: 13px;
`);
settings.theme = `
.sk_theme #sk_omnibarSearchArea input, #sk_omnibarSearchResult {
  font-size: 15px;
}
`;

// Search engine configuration
const SEARCH_ENGINE = "https://kagi.com/search?q=";
api.addSearchAlias("k", "kagi", SEARCH_ENGINE, "s");
settings.defaultSearchEngine = "k";

// URL and clipboard operations
api.mapkey("ymd", "Copy current page URL as Markdown link", () =>
  api.Clipboard.write(`[${document.title}](${window.location.href})`),
);

function parseHttpUrl(text) {
  const hasHttpScheme = /^https?:\/\//i.test(text);
  const candidate = hasHttpScheme ? text : `https://${text}`;

  try {
    const url = new URL(candidate);
    const isLikelyHost =
      hasHttpScheme ||
      (!(url.username || url.password) &&
        (url.hostname === "localhost" || url.hostname.includes(".") || url.hostname.startsWith("[")));
    return ["http:", "https:"].includes(url.protocol) && isLikelyHost ? url.href : null;
  } catch {
    return null;
  }
}

// Error handling for clipboard operations
function handleClipboardError(error) {
  api.Front.showBanner(`Failed to access clipboard: ${error?.message ?? String(error)}`, 3000);
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

    const url = parseHttpUrl(clipText);
    markInfo.url = url ?? `${SEARCH_ENGINE}${encodeURIComponent(clipText)}`;

    api.RUNTIME("openLink", markInfo);
  } catch (error) {
    handleClipboardError(error);
  }
}

// Clipboard URL opening mappings
function openClipboardText(openInNewTab) {
  try {
    api.Clipboard.read((response) => {
      const clipText = response?.data?.trim();
      if (clipText) {
        processClipboardText(clipText, openInNewTab);
      } else {
        handleClipboardError(new Error("No content in clipboard"));
      }
    });
  } catch (error) {
    handleClipboardError(error);
  }
}

api.mapkey("go", "Open URL in clipboard", () => openClipboardText(false));
api.mapkey("gO", "Open URL in clipboard in new tab", () => openClipboardText(true));

// Timeout durations for PassThrough mode
const TIMEOUT_SHORT_MS = 1500;
const TIMEOUT_LONG_MS = 300000;

api.mapkey("p", "Enter PassThrough mode", () => {
  const seconds = TIMEOUT_SHORT_MS / 1000;
  api.Front.showBanner(`PassThrough exits after ${seconds}s without a keypress, or when ESC is pressed`, 1600);
  api.Normal.passThrough(TIMEOUT_SHORT_MS);
});

api.mapkey("P", "Enter PassThrough mode", () => {
  const seconds = TIMEOUT_LONG_MS / 1000;
  api.Front.showBanner(`PassThrough exits after ${seconds}s without a keypress, or when ESC is pressed`, 1600);
  api.Normal.passThrough(TIMEOUT_LONG_MS);
});

api.map("<Ctrl-u>", "e");
api.map("<Ctrl-d>", "d");

const KAGI_RE = siteUrlPattern(["kagi.com"]);
api.unmap("?", KAGI_RE);
api.unmap("h", KAGI_RE); // Navigation
api.unmap("j", KAGI_RE); // Navigation
api.unmap("k", KAGI_RE); // Navigation
api.unmap("l", KAGI_RE); // Navigation
api.unmap("/", KAGI_RE); // Search
api.unmap("q", KAGI_RE); // Open quick answer
api.unmap("s", KAGI_RE); // Site info; also removes Surfingkeys mappings prefixed with s

const X_RE = siteUrlPattern(["x.com"]);
api.unmap("?", X_RE);
api.unmap("j", X_RE); // Navigation
api.unmap("k", X_RE); // Navigation
api.unmap("g", X_RE); // Navigation; also removes Surfingkeys mappings prefixed with g
api.unmap("/", X_RE); // Search
api.unmap(".", X_RE); // Refresh
api.unmap("n", X_RE); // New post
api.unmap("m", X_RE); // New direct message
api.unmap("l", X_RE); // Like
api.unmap("r", X_RE); // Reply
api.unmap("s", X_RE); // Share post; also removes Surfingkeys mappings prefixed with s
api.unmap("u", X_RE); // Mute account

const LIMITED_DOMAINS = [
  "app.graphite.com",
  "boot.dev",
  "excalidraw.com",
  "exe.dev",
  "feishu.cn",
  "figma.com",
  "linear.app",
  "motherduck.com",
  "notion.so",
  "photos.google.com",
  "roamresearch.com",
  "sshx.io",
];

const LIMITED_RE = siteUrlPattern(LIMITED_DOMAINS);

const KEEP_KEYS = ["e", "d", "E", "R", "B", "F", "S", "D", "t", "T", "p", "P"];

api.unmapAllExcept(KEEP_KEYS, LIMITED_RE);
api.map("<Ctrl-u>", "e", LIMITED_RE);
api.map("<Ctrl-d>", "d", LIMITED_RE);
