if test -d /opt/homebrew
  #################### Homebrew ####################
  /opt/homebrew/bin/brew shellenv | source

  #################### Mise ####################
  mise activate fish | source
end

if status is-interactive
  set -g fish_greeting

  #################### Private Env ####################
  if test -f $HOME/dotfiles/config/shell/env.private.fish
    source $HOME/dotfiles/config/shell/env.private.fish
  end

  #################### Keybindings ####################
  bind \cs edit_command_buffer

  #################### Starship ####################
  starship init fish | source

  #################### Zoxide ####################
  zoxide init fish --cmd j | source

  #################### Television ####################
  tv init fish | source

  #################### Cancel Commandline ####################
  function cancel-commandline
      commandline -C 2147483647
      for i in (seq (commandline -L))
          echo '^C'
      end
      commandline ""
  end

  bind \cc cancel-commandline

  #################### Editor ####################
  if not set -q VISUAL
    set -g VISUAL "zed --wait"
  end

  if not set -q EDITOR
    set -g EDITOR "zed --wait"
  end

  #################### Yazi ####################
  function y
    set tmp (mktemp -t "yazi-cwd.XXXXXX")
    yazi $argv --cwd-file="$tmp"
    if set cwd (command cat -- "$tmp"); and [ -n "$cwd" ]; and [ "$cwd" != "$PWD" ]
      builtin cd -- "$cwd"
    end
    rm -f -- "$tmp"
  end

  #################### Tailspin ####################
  set -g TAILSPIN_PAGER "ov -f [FILE]"

  fish_add_path $HOME/dev/prototypes/utils/bin
  fish_add_path $HOME/dev/prototypes/utils/scripts

  for file in $HOME/dotfiles/home/.config/fish/completions/*.fish
    source $file
  end

  #################### Aliases ####################
  source $HOME/dotfiles/config/shell/aliases.fish

  #################### Functions ####################
  source $HOME/dotfiles/config/shell/functions/atuin.fish
  source $HOME/dotfiles/config/shell/functions/macos.fish
  source $HOME/dotfiles/config/shell/functions/utils.fish
end
