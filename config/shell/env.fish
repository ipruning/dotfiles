if test -d /opt/homebrew
  /opt/homebrew/bin/brew shellenv | source
end

if type -q mise
  mise activate fish | source
end

if status is-interactive
  # 👇 Greeting
  set -g fish_greeting

  # 👇 Keybindings
  # bind \cs edit_command_buffer

  # 👇 Starship
  # if type -q starship
  #   starship init fish | source
  # end

  # 👇 Zoxide
  # if type -q zoxide
  #   zoxide init fish --cmd j | source
  # end

  # 👇 Television
  # if type -q tv
  #   tv init fish | source
  # end

  # 👇 Cancel Commandline
  # function cancel-commandline
  #     commandline -C 2147483647
  #     for i in (seq (commandline -L))
  #         echo '^C'
  #     end
  #     commandline ""
  # end

  # bind \cc cancel-commandline

  # 👇 Yazi
  # function y
  #   set tmp (mktemp -t "yazi-cwd.XXXXXX")
  #   yazi $argv --cwd-file="$tmp"
  #   if set cwd (command cat -- "$tmp"); and [ -n "$cwd" ]; and [ "$cwd" != "$PWD" ]
  #     builtin cd -- "$cwd"
  #   end
  #   rm -f -- "$tmp"
  # end
end
