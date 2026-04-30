# 👇 Linux
alias ...="cd ../.."

alias ..="cd .."

alias df="df -h"

alias du="du -h"

alias free="free -h"

alias grep="grep --color=auto"

# BSD ls (macOS default) doesn't accept --color=auto
if [[ $OSTYPE == darwin* ]]; then
  alias ls="ls -G"
else
  alias ls="ls --color=auto"
fi

alias q="exit"

alias rsyncssh="rsync -Pr --rsh=ssh"

alias cdr='cd $(git rev-parse --show-toplevel)'

# 👇 macOS
if [[ $OSTYPE == darwin* ]]; then
  alias jr="jump-to-repo"

  alias js="jump-to-session"

  alias keyboardmaestro='/Applications/Keyboard Maestro.app/Contents/MacOS/keyboardmaestro'

  alias surge="/Applications/Surge.app/Contents/Applications/surge-cli"
fi

jt () {
  local d saved_umask
  d="$(mktemp -d -t tempe.XXXXXXXX)" || return
  saved_umask=$(umask)
  umask 077
  builtin cd "$d" || { umask "$saved_umask"; return; }
  if [[ $# -eq 1 ]]; then
    mkdir -m 700 -p -- "$1" && builtin cd -- "$1"
  fi
  umask "$saved_umask"
  pwd
}

mcd () {
  [[ -z "${1:-}" ]] && return 2
  mkdir -p -- "$1" && cd -- "$1"
}

y () {
  local tmp cwd
  tmp="$(mktemp -t "yazi-cwd.XXXXXX")" || return
  yazi "$@" --cwd-file="$tmp"
  if cwd="$(command cat -- "$tmp")" && [ -n "$cwd" ] && [ "$cwd" != "$PWD" ]; then
    builtin cd -- "$cwd"
  fi
  rm -f -- "$tmp"
}

note() {
  if [[ $# -eq 0 ]]; then
    cat ~/.sticky_note 2>/dev/null || echo "No note set"
  elif [[ "$1" == "-c" ]]; then
    rm -f ~/.sticky_note
  else
    echo "$*" > ~/.sticky_note
  fi
}

alias -s md="bat"
alias -s txt="bat"

alias -g DN='> /dev/null'
alias -g NE='2>/dev/null'
alias -g NUL='>/dev/null 2>&1'

alias -g JQ='| jq'

alias -g C='| c'
alias -g P='p |'

exe-dev-switch() {
  emulate -L zsh

  # IdentityFile intentionally points at the .pub key; the matching private
  # key lives in the 1Password SSH agent, not on disk.
  local conf="$HOME/.ssh/exe-dev-profile.conf"

  local -a names
  local p name
  for p in "$HOME"/.ssh/exe-dev-*.pub(N); do
    name="${${p:t:r}#exe-dev-}"
    [[ "$name" == "profile" ]] && continue
    names+=("$name")
  done

  if (( ${#names} == 0 )); then
    print -u2 'exe-dev-switch: no ~/.ssh/exe-dev-*.pub found'
    return 1
  fi

  local current=""
  if [[ -r "$conf" ]]; then
    current="$(awk '/^[[:space:]]*IdentityFile[[:space:]]+/ {print $2; exit}' "$conf")"
    current="${${current:t:r}#exe-dev-}"
  fi

  local target="$1"
  if [[ -z "$target" ]]; then
    if (( ${#names} == 1 )); then
      target="${names[1]}"
    elif (( ${#names} == 2 )); then
      if [[ "$current" == "${names[1]}" ]]; then
        target="${names[2]}"
      else
        target="${names[1]}"
      fi
    else
      print -u2 "usage: exe-dev-switch {${(j:|:)names}}${current:+  (current: $current)}"
      return 2
    fi
  fi

  if ! (( ${names[(Ie)$target]} )); then
    print -u2 "exe-dev-switch: unknown profile '$target' (available: ${(j:, :)names})"
    return 2
  fi

  if [[ "$target" == "$current" ]]; then
    print "exe-dev: already on $target"
    return 0
  fi

  local pub="$HOME/.ssh/exe-dev-$target.pub"
  local tmp="$conf.tmp.$$"

  cat > "$tmp" <<EOF
Host exe.dev *.exe.xyz
  IdentitiesOnly yes
  IdentityFile $pub
EOF

  chmod 600 "$tmp"
  mv "$tmp" "$conf"

  print "exe-dev: ${current:-?} -> $target"
}
