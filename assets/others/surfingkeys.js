api.addSearchAlias('k', 'kagi', 'https://kagi.com/search?q=', 's');
settings.defaultSearchEngine = 'k';

// settings.tabsThreshold = 0;
settings.focusAfterClosed = 'last';
settings.focusFirstCandidate = true;
settings.hintAlign = 'left';
settings.modeAfterYank = 'Normal';
settings.omnibarPosition = 'bottom';

api.Hints.style(`
  font-family: 'MonoLisa Nerd Font', monospace;
  font-size: 12px;
`);

api.mapkey('<Ctrl-d>', 'Scroll down half page', function () {
  api.Normal.scroll('pageDown');
});
api.mapkey('<Ctrl-u>', 'Scroll up half page', function () {
  api.Normal.scroll('pageUp');
});
api.mapkey('ym', 'Copy current page URL as Markdown link', function () {
  api.Clipboard.write('[' + document.title + '](' + window.location.href + ')');
});

api.mapkey('p', 'Open URL in clipboard', function () {
  api.Clipboard.read((response) => {
    const clipText = response.data;
    var markInfo = {
      scrollLeft: 0,
      scrollTop: 0
    };
    markInfo.tab = {
      tabbed: false,
      active: false
    };
    if (clipText.indexOf(".") != -1) {
      markInfo.url = clipText;
    } else {
      markInfo.url = "https://kagi.com/search?q=" + encodeURIComponent(clipText);
    }
    api.RUNTIME("openLink", markInfo)
  });
});
api.mapkey('P', 'Open URL in clipboard at new tab', function () {
  api.Clipboard.read((response) => {
    const clipText = response.data;
    markInfo = {
      scrollLeft: 0,
      scrollTop: 0
    };
    markInfo.tab = {
      tabbed: true,
      active: true
    };
    if (clipText.indexOf(".") != -1) {
      markInfo.url = clipText;
    } else {
      markInfo.url = "https://kagi.com/search?q=" + encodeURIComponent(clipText);
    }
    api.RUNTIME("openLink", markInfo)
  });
});

// Choose a buffer/tab
// api.map('b', 'T');

// Open a URL in current tab
// api.map('o', 'go');

// Edit current URL, and open in same tab
// api.map('O', ';U');

// Edit current URL, and open in new tab
// api.map('T', ';u');

api.unmapAllExcept(['<Ctrl-d>', '<Ctrl-u>', 'E', 'R', 'e', 'd', 'S', 'D', 'x'], /roamresearch\.com|notion\.so|feishu\.cn|kagi\.com/i);
