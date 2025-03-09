if test -d /opt/homebrew
    /opt/homebrew/bin/brew shellenv | source
    mise activate fish | source
end


if status is-interactive
    set -g fish_greeting

    starship init fish | source

    zoxide init fish --cmd j | source

    tv init fish | source
    
    atuin init fish --disable-up-arrow | source

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

    # Linux Aliases Part 1
    alias cp="cp -i"
    alias df="df -h"
    alias du="du -h"
    alias egrep="egrep --color=auto"
    alias fgrep="fgrep --color=auto"
    alias free="free -h"
    alias grep="grep --color=auto"
    alias ls="ls --color=auto"
    alias mkdir="mkdir -p"
    alias mv="mv -i"
    alias rm="rm -i"

    # Linux Aliases Part 2
    alias ...="cd ../.."
    alias ..="cd .."
    alias hg="history | grep"
    alias ll="ls -lAh"
    alias ports="ss -tulpn"

    # macOS Aliases Part 1
    alias c="pbcopy"
    alias g="git"
    alias keyboardmaestro="/Applications/Keyboard\ Maestro.app/Contents/MacOS/keyboardmaestro"
    alias ll="eza --all --git --group-directories-first --header --long --time-style long-iso"
    alias lt="eza --all --git --group-directories-first --header --long --time-style long-iso --tree"
    alias o="open ."
    alias p="pbpaste"
    alias ports="viddy --interval 1s 'lsof -i @127.0.0.1 | grep LISTEN'"
end
