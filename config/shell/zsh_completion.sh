#===============================================================================
# 👇 zsh-completions
# if you are using a custom compinit setup with a ZSH Framework, ensure compinit is below your sourcing of the framework
#===============================================================================
autoload -Uz compinit && compinit

#===============================================================================
# 👇 completions
# if you are using a custom compinit setup with a ZSH Framework, ensure compinit is below your sourcing of the framework
#===============================================================================
case $SYSTEM_TYPE in
mac_arm64 | mac_x86_64)
  #===============================================================================
  # 👇 1password completions
  #===============================================================================
  eval "$(op completion zsh)"
  compdef _op op

  #===============================================================================
  # 👇 cz completions
  #===============================================================================
  eval "$(register-python-argcomplete cz)"

  #===============================================================================
  # 👇 pipx completions
  #===============================================================================
  eval "$(register-python-argcomplete pipx)"

  #===============================================================================
  # 👇 zoxide completions
  #===============================================================================
  eval "$(zoxide init zsh)"
  ;;
raspberry) ;;
esac
