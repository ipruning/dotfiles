if test -d /opt/homebrew
  /opt/homebrew/bin/brew shellenv | source
  mise activate fish | source
end

if status is-interactive
  set -g fish_greeting

  if test -f $HOME/dotfiles/config/shell/env.private.fish
    source $HOME/dotfiles/config/shell/env.private.fish
  end

  starship init fish | source

  zoxide init fish --cmd j | source

  tv init fish | source

  bind \cs edit_command_buffer

  function cancel-commandline
      commandline -C 2147483647
      for i in (seq (commandline -L))
          echo '^C'
      end
      commandline ""
  end

  if not set -q VISUAL
    set -g VISUAL "zed --wait"
  end

  if not set -q EDITOR
    set -g EDITOR "zed --wait"
  end

  bind \cc cancel-commandline

  function y
    set tmp (mktemp -t "yazi-cwd.XXXXXX")
    yazi $argv --cwd-file="$tmp"
    if set cwd (command cat -- "$tmp"); and [ -n "$cwd" ]; and [ "$cwd" != "$PWD" ]
      builtin cd -- "$cwd"
    end
    rm -f -- "$tmp"
  end

  fish_add_path $HOME/Developer/prototypes/utils/bin
  fish_add_path $HOME/Developer/prototypes/utils/scripts

  for file in $HOME/dotfiles/home/.config/fish/completions/*.fish
    source $file
  end

  source $HOME/dotfiles/config/shell/aliases.fish
  source $HOME/dotfiles/config/shell/functions/atuin.fish
  source $HOME/dotfiles/config/shell/functions/utils.fish
end
