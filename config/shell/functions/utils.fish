function upgrade-all
    set_color green; echo "Updating Homebrew..."; set_color normal
    if command -v brew >/dev/null
        brew update
        brew upgrade
        set_color green; echo "Pruning Homebrew..."; set_color normal
        brew cleanup
        brew autoremove
    end

    set_color green; echo "Updating mise..."; set_color normal
    if command -v mise >/dev/null
        mise upgrade

        set_color green; echo "Pruning mise..."; set_color normal
        mise prune
        mise reshim
    end

    set_color green; echo "Upgrading GitHub CLI extensions..."; set_color normal
    if command -v gh >/dev/null
        gh extension upgrade --all
    end

    set_color green; echo "Updating tldr pages..."; set_color normal
    if command -v tldr >/dev/null
        tldr --update
    end

    set_color green; echo "Backing up all packages..."; set_color normal
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
