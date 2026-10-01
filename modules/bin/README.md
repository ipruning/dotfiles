# Independent commands

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
are authoritative for options; this index is not a second option reference.

| Command / source | Purpose | Dependencies beyond Bash or Python/uv | Normal effects |
| --- | --- | --- | --- |
| [amp-ghostty](amp-ghostty) | Open a three-pane development layout | macOS, Ghostty 1.3+ with macos-applescript enabled, Accessibility/Automation permission, osascript, amp, lazygit, yazi | Interactive/UI; creates a tab and splits; sends commands to new terminals, leaves clipboard unchanged, and focuses the amp pane |
| [autocorrect.py](autocorrect.py) | Format Chinese plain text, not Markdown | autocorrect-py | Read files/stdin; write stdout |
| [c](c) | Copy stdin | pbcopy, xclip, or putclip | Write clipboard |
| [chatgpt.py](chatgpt.py) | Send a composed message to ChatGPT in Chrome | fire; macOS, Chrome, Accessibility permission, pbcopy, osascript | Write clipboard; UI/network submission; dry_run writes stdout only |
| [d](d) | Open Docker manager | lazydocker, Docker access; delegated options: `lazydocker --help` | Interactive; can mutate Docker resources |
| [dateutc](dateutc) | Print UTC timestamp | date | Read-only; stdout |
| [g](g) | Open Git manager | lazygit, Git; delegated options: `lazygit --help` | Interactive; can mutate Git state/files |
| [get-codex-dump.py](get-codex-dump.py) | Export Codex logs as tagged text | typer | Read logs; stdout or write chosen output file |
| [get-transcript.py](get-transcript.py) | Fetch a YouTube transcript | youtube-transcript-api, network | Network read; stdout |
| [histx](histx) | Show shell history | atuin, or readable HISTFILE and tail | Read history; stdout |
| [link.py](link.py) | Select links, paths, UUIDs, or resume commands from text | loguru, rich, fzf; optional Zellij screen; macOS open or pbcopy for selected action | Read stdin/screen; interactive selection then open a path/URL or copy a UUID/command to clipboard |
| [mkbir](mkbir) | Create a bird-named folder | mkdir, rmdir, mktemp, mv; sleep on lock contention | Write folder and ~/.bird_count; temporary counter lock/file |
| [newwin](newwin) | Open a supported application's new window | macOS, selected application, open or osascript; Accessibility permission for UI automation | Interactive/UI |
| [o](o) | Open a path or URL | macOS open or Linux xdg-open | Interactive/UI; may launch an application |
| [p](p) | Print clipboard text | pbpaste, xclip, or getclip | Read clipboard; stdout |
| [pi-session-export.py](pi-session-export.py) | Convert Pi exports to raw and turns JSONL | Python standard library | Read input; write output JSONL files/directories |
| [pi-tmux](pi-tmux) | Create/attach the current directory's Pi session | git, tmux, zsh, pi | Interactive; create sessions/windows or attach/switch |
| [pi-zellij](pi-zellij) | Create/attach the current directory's Pi session | git, zellij and its configured pi layout/tools | Interactive; create or attach session |
| [pmt.py](pmt.py) | Compose tagged instructions/context | Python standard library | Read files/stdin; write stdout |
| [ports](ports) | List listening sockets once | Linux ss or macOS lsof; viddy only for explicit --watch | Read-only snapshot by default; --watch is interactive |
| [repoprompt](repoprompt) | Open the current directory in Repo Prompt | macOS, open, Repo Prompt | Interactive/UI |
| [scratch](scratch) | Edit a retained temporary file | mktemp; VISUAL/EDITOR or cursor/code/nvim/vim/vi | Write temporary file; interactive editor |
| [skillshare-source](skillshare-source) | Inspect/register/switch Skillshare sources and export descriptions | typer, rich, ruamel.yaml; skillshare for active-source queries | Reads config/skills; add/rm/switch write config; exec temporarily writes config and runs a supplied command |
| [ttok](ttok) | Count o200k_base tokens in text/files | tiktoken | Read files/stdin; stdout; first tokenization may download/cache encoding data |
| [zed-image-paste](zed-image-paste) | Save a clipboard image and copy its Markdown link | macOS, osascript, pbcopy, python3; Zed task environment | Write image/directory and clipboard |
