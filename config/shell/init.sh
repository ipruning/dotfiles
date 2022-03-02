#!/bin/bash

#===============================================================================
# 👇 zprof
#===============================================================================
# zmodload zsh/zprof # 在 ~/.zshrc 的头部加上这个，加载 profile 模块

#===============================================================================
# 👇 _INIT_SH_LOADED
#===============================================================================
if [ -z "$_INIT_SH_LOADED" ]; then
    _INIT_SH_LOADED=1
else
    return
fi

#===============================================================================
# 👇 env
#===============================================================================
if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    # run script for interactive mode of bash/zsh
    if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
        if [ -f "$HOME/dotfiles/config/shell/zsh_env" ]; then
            . "$HOME/dotfiles/config/shell/zsh_env"
        fi
    fi
fi

#===============================================================================
# 👇 functions
#===============================================================================
if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    # run script for interactive mode of bash/zsh
    if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
        if [ -f "$HOME/dotfiles/config/shell/zsh_functions" ]; then
            . "$HOME/dotfiles/config/shell/zsh_functions"
        fi
    fi
fi

#===============================================================================
# 👇 aliases
#===============================================================================
if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    # run script for interactive mode of bash/zsh
    if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
        if [ -f "$HOME/dotfiles/config/shell/zsh_aliases" ]; then
            . "$HOME/dotfiles/config/shell/zsh_aliases"
        fi
    fi
fi

#===============================================================================
# 👇 completion
#===============================================================================
if [ -n "$BASH_VERSION" ] || [ -n "$ZSH_VERSION" ]; then
    # run script for interactive mode of bash/zsh
    if [[ $- == *i* ]] && [ -z "$_INIT_SH_NOFUN" ]; then
        if [ -f "$HOME/dotfiles/config/shell/zsh_completion" ]; then
            . "$HOME/dotfiles/config/shell/zsh_completion"
        fi
    fi
fi

#===============================================================================
# 👇 zprof
#===============================================================================
# zprof
