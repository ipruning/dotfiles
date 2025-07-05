function repo-fork-sync
  gh repo list --fork --visibility public --json owner,name | jq -r 'map(.owner.login + "/" + .name) | .[]' | xargs -t -L1 gh repo sync
end

function x86_64-zsh-login
  arch -x86_64 zsh --login
end

function x86_64-zsh-run
  arch -x86_64 zsh -c $argv
end

function jump-to-session
  if test -n "$ZELLIJ"
  else
    if test "$TERM_PROGRAM" = "ghostty"
      set zj_sessions (/opt/homebrew/bin/zellij list-sessions --no-formatting --short)
      set session_count (echo "$zj_sessions" | grep -c '^.')

      if test $session_count -eq 0
        /opt/homebrew/bin/zellij
      else
        set selected_session (echo "$zj_sessions" | /opt/homebrew/bin/tv --no-preview)
        if test -n "$selected_session"
          /opt/homebrew/bin/zellij attach "$selected_session"
        end
      end
    end
  end
end

function jump-to-repo
  set repo_path (tv git-repos)
  if test -z "$repo_path"
    return
  end

  if test -n "$ZELLIJ"
    cd "$repo_path"
  else
    cd "$repo_path"
    set repo_name (basename "$repo_path")
    zellij attach "$repo_name" 2>/dev/null || zellij --session "$repo_name"
  end
end
