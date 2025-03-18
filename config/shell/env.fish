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

  function cancel-commandline
      commandline -C 2147483647
      for i in (seq (commandline -L))
          echo '^C'
      end
      commandline ""
  end

  bind \cc cancel-commandline
  bind \cs edit_command_buffer

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

  register-python-argcomplete --shell fish ttok.py | source

  source $HOME/dotfiles/config/shell/aliases.fish
  source $HOME/dotfiles/config/shell/functions/atuin.fish
  source $HOME/dotfiles/config/shell/functions/utils.fish
end
