# 👇 case-insensitive matching
zstyle ":completion:*" matcher-list "m:{a-z}={A-Za-z}"

# 👇 fzf-tab
zstyle ':completion:*:descriptions' format '[%d]'
zstyle ':completion:*' menu no
zstyle ':fzf-tab:*' use-fzf-default-opts yes

# 👇 exe.dev hosts
_exe_hosts() {
    reply=(${(f)"$(ssh exe.dev ls --json 2>/dev/null | jq -r '.vms[].ssh_dest')"})
}
zstyle -e ':completion:*:(ssh|scp|rsync):*' hosts '_exe_hosts'
