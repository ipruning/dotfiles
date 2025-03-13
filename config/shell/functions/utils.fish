function logger
    # /// ChangeLog
    # 001 - AI - Rewrote logger function with improved structure, more color options, and better documentation
    # 002 - AI - Fixed color output by removing quotes around ANSI escape sequences
    # 003 - AI - Fixed formatting and color issues by properly defining ANSI escape sequences
    # 004 - AI - Fixed the printf format to ensure correct output formatting
    # ///
    
    set -l RED (echo -e "\033[0;31m")     # Error
    set -l GREEN (echo -e "\033[0;32m")   # Success
    set -l YELLOW (echo -e "\033[1;33m")  # Warning
    set -l BLUE (echo -e "\033[0;34m")    # Debug
    set -l MAGENTA (echo -e "\033[0;35m") # Critical
    set -l CYAN (echo -e "\033[0;36m")    # Notice
    set -l GRAY (echo -e "\033[0;90m")    # Info
    set -l NC (echo -e "\033[0m")         # Reset color

    set -l message $argv[1]
    set -l loglevel $argv[2]
    
    if test -z "$loglevel"
        set loglevel "INFO"
    end
    
    set -l timestamp (date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    set -l upper_loglevel (string upper $loglevel)
    
    set -l color $GRAY
    switch $upper_loglevel
        case "ERROR"
            set color $RED
        case "WARN" "WARNING"
            set color $YELLOW
        case "INFO"
            if test "$DRY_RUN" = true
                set color $YELLOW
            else
                set color $GRAY
            end
        case "SUCCESS"
            set color $GREEN
        case "DEBUG"
            set color $BLUE
        case "CRITICAL"
            set color $MAGENTA
        case "NOTICE"
            set color $CYAN
        case '*'
            set loglevel "INFO"
            set color $GRAY
    end
    
    printf "$color[%s] [%s] %s$NC\n" $timestamp $upper_loglevel $message
end

function upgrade-all
    logger "Updating Homebrew..."
    if command -v brew >/dev/null
        brew update
        brew upgrade
        logger "Pruning Homebrew..."
        brew cleanup
        brew autoremove
    end

    logger "Updating mise..."
    if command -v mise >/dev/null
        mise upgrade

        logger "Pruning mise..."
        mise prune
        mise reshim
    end

    logger "Upgrading GitHub CLI extensions..."
    if command -v gh >/dev/null
        gh extension upgrade --all
    end

    logger "Updating tldr pages..."
    if command -v tldr >/dev/null
        tldr --update
    end

    logger "Backing up all packages..."
    set -l host (hostname -s)
    if command -v brew >/dev/null
        brew bundle dump --file="$HOME/dotfiles/config/packages/brew_dump.$host.txt" --force
        brew leaves >"$HOME/dotfiles/config/packages/brew_leaves.$host.txt"
        brew list --installed-on-request >"$HOME/dotfiles/config/packages/brew_installed.$host.txt"
    end
    if command -v gh >/dev/null
        gh extension list | awk '{print $3}' >"$HOME/dotfiles/config/packages/gh_extensions.$host.txt"
    end
    if test -d "/Applications"
        find /Applications -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME/dotfiles/config/packages/macos_applications.$host.txt"
    end
    if test -d "/Applications/Setapp"
        find /Applications/Setapp -maxdepth 1 -name "*.app" -exec basename {} .app \; | sort >"$HOME/dotfiles/config/packages/macos_setapp.$host.txt"
    end
end
