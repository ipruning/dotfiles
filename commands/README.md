# Commands

Start with the linked source or `<command> --help`, not a bare invocation:
several commands immediately launch an editor, application, or session, or write
files and the clipboard. Help does not perform those command actions.

Python commands use `uv run --script` shebangs with inline dependencies. That
launcher may download tools/dependencies and write caches even for help. For
discovery without provisioning, read the source, or use an already-provisioned
Python interpreter with the declared dependencies. Shell commands require Bash;
their help does not require the optional tools listed below. Other dependencies
are never installed by these commands. Prefer `--help` (Typer commands need not
support `-h`).

Effects below describe normal execution, not help. **Interactive** commands can
change application state through the tools they launch. Source and owner help
are authoritative for options.

| Command / source | Purpose | Dependencies beyond Bash or Python/uv | Normal effects |
| --- | --- | --- | --- |
| [amp-ghostty](amp-ghostty) | Open a three-pane development layout | macOS, Ghostty 1.3+ with macos-applescript enabled, Accessibility/Automation permission, osascript, amp, lazygit, yazi | Interactive/UI; creates a tab and splits; sends commands to new terminals, leaves clipboard unchanged, and focuses the amp pane |
| [autocorrect-text](autocorrect-text) | Format Chinese plain text, not Markdown | autocorrect-py | Read files/stdin; write stdout |
| [c](c) | Copy stdin | pbcopy, xclip, or putclip | Write clipboard |
| [chatgpt](chatgpt) | Send a composed message to ChatGPT in Chrome | fire; macOS, Chrome, Accessibility permission, pbcopy, osascript | Write clipboard; UI/network submission; --dry-run writes stdout only |
| [d](d) | Open Docker manager | lazydocker, Docker access; delegated options: `lazydocker --help` | Interactive; can mutate Docker resources |
| [dateutc](dateutc) | Print UTC timestamp | date | Read-only; stdout |
| [g](g) | Open Git manager | lazygit, Git; delegated options: `lazygit --help` | Interactive; can mutate Git state/files |
| [get-codex-dump](get-codex-dump) | Export Codex logs as tagged text | typer | Read logs; stdout or write chosen output file |
| [get-transcript](get-transcript) | Fetch a YouTube transcript | youtube-transcript-api, network | Network read; stdout |
| [`link`](link) | Select links, paths, UUIDs, or resume commands from text | loguru, rich, fzf; optional Zellij screen; macOS open or pbcopy for selected action | Read stdin/screen; interactive selection then open a path/URL or copy a UUID/command to clipboard |
| [mkbir](mkbir) | Create a bird-named folder | mkdir, rmdir, mktemp, mv; sleep on lock contention | Write folder and ~/.bird_count; temporary counter lock/file |
| [o](o) | Open a path or URL | macOS open or Linux xdg-open | Interactive/UI; may launch an application |
| [p](p) | Print clipboard text | pbpaste, xclip, or getclip | Read clipboard; stdout |
| [pi-session-export](pi-session-export) | Convert Pi exports to raw and turns JSONL | Python standard library | Read input; write output JSONL files/directories |
| [pi-tmux](pi-tmux) | Create/attach the current directory's Pi session | git, tmux, zsh, pi | Interactive; create sessions/windows or attach/switch |
| [pmt](pmt) | Compose tagged instructions/context | Python standard library | Read files/stdin; write stdout |
| [ports](ports) | List listening sockets once | Linux ss or macOS lsof; viddy only for explicit --watch | Read-only snapshot by default; --watch is interactive |
| [repoprompt](repoprompt) | Open the current directory in Repo Prompt | macOS, open, Repo Prompt | Interactive/UI |
| [scratch](scratch) | Edit a retained temporary file | mktemp; VISUAL/EDITOR or cursor/code/nvim/vim/vi | Write temporary file; interactive editor |
| [skillshare-source](skillshare-source) | Inspect/register/switch Skillshare sources and export descriptions | typer, rich, ruamel.yaml; skillshare for active-source queries | Reads config/skills; add/rm/switch write config; exec temporarily writes config and runs a supplied command |
| [ttok](ttok) | Count o200k_base tokens in text/files | tiktoken | Read files/stdin; stdout; first tokenization may download/cache encoding data |
| [zed-image-paste](zed-image-paste) | Save a clipboard image and copy its Markdown link | macOS, osascript, pbcopy, python3; Zed task environment | Write image/directory and clipboard |
