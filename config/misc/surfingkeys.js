// settings.digitForRepeat = false;
settings.focusAfterClosed = 'last';        // Focus last viewed tab when closing current tab
settings.focusFirstCandidate = true;       // Focus first item in omnibar
settings.hintAlign = 'left';               // Align link hints to the left
settings.modeAfterYank = 'Normal';         // Return to Normal mode after yanking
settings.omnibarMaxResults = 5;
// settings.omnibarPosition = 'bottom';
settings.tabsThreshold = 0;                // Always use omnibar for tab selection

api.Hints.style(`
  font-family: MonoLisa Nerd Font;
`);
settings.theme = `
.sk_theme #sk_omnibarSearchArea input, #sk_omnibarSearchResult {
  font-size: 14px;
}
`;

// Search engine configuration
const SEARCH_ENGINE = 'https://kagi.com/search?q=';
api.addSearchAlias('k', 'kagi', SEARCH_ENGINE, 's');
settings.defaultSearchEngine = 'k';

// Scrolling controls
api.mapkey('<Ctrl-d>', 'Scroll down half page', () => api.Normal.scroll('pageDown'));
api.mapkey('<Ctrl-u>', 'Scroll up half page', () => api.Normal.scroll('pageUp'));

// URL and clipboard operations
api.mapkey('ym', 'Copy current page URL as Markdown link', () => api.Clipboard.write(`[${document.title}](${window.location.href})`));

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
        active: openInNewTab
      }
    };

    // If text is a valid URL, open it directly (adding https:// if needed)
    // Otherwise, use it as a search query
    if (URL_PATTERN.test(clipText)) {
      markInfo.url = clipText.startsWith('http') ? clipText : `https://${clipText}`;
    } else {
      markInfo.url = `${SEARCH_ENGINE}${encodeURIComponent(clipText)}`;
    }

    api.RUNTIME("openLink", markInfo);
  } catch (error) {
    handleClipboardError(error);
  }
}

// Clipboard URL opening mappings
api.mapkey('go', 'Open URL in clipboard', () => api.Clipboard.read((response) => {
  if (response?.data) {
    processClipboardText(response.data.trim(), false);
  } else {
    handleClipboardError(new Error('No content in clipboard'));
  }
}));

api.mapkey('gO', 'Open URL in clipboard in new tab', () => api.Clipboard.read((response) => {
  if (response?.data) {
    processClipboardText(response.data.trim(), true);
  } else {
    handleClipboardError(new Error('No content in clipboard'));
  }
}));

// Timeout durations for PassThrough mode
const TIMEOUT_SHORT_MS = 1000;
const TIMEOUT_LONG_MS = 300000;

api.mapkey('p', 'Enter PassThrough mode', () => {
  const seconds = TIMEOUT_SHORT_MS / 1000;
  api.Front.showBanner(
    `Entering PassThrough mode for ${seconds}s, press ESC to exit early`,
    1600
  );
  api.Normal.passThrough(TIMEOUT_SHORT_MS);
});

api.mapkey('P', 'Enter PassThrough mode', () => {
  const seconds = TIMEOUT_LONG_MS / 1000;
  api.Front.showBanner(
    `Entering PassThrough mode for ${seconds}s, press ESC to exit early`,
    1600
  );
  api.Normal.passThrough(TIMEOUT_LONG_MS);
});

// Map gt to T
api.map('gt', 'T');

// Keep only essential mappings for specific sites
const ROOT_DOMAINS = [
  'feishu.cn',
  'kagi.com',
  'monkeytype.com',
  'notion.so',
  'roamresearch.com',
  'x.com',
];

const EXCLUDED_DOMAINS = new RegExp(
  `\\b(${ROOT_DOMAINS.map(domain => domain.replace('.', '\\.')).join('|')})\\b`,
  'i'
);

api.unmapAllExcept([
  // Scrolling
  '<Ctrl-d>', '<Ctrl-u>', 'e', 'd',
  // Navigation
  'E', 'R',
  // Tabs
  'S', 'D', 'x', 'X', 't', 'T', 'B',
  // Misc
  'f', 'F', 'i', 'p', 'P'
], EXCLUDED_DOMAINS);
