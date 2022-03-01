# dotfiles

My dotfiles

## 系统配置

- 修改用户名密码；
- 启用触摸板轻触；
- 启用三指拖移；
- 取消自动重新排列空间；
- 启用 Tab 键移动焦点；
- 修改共享电脑名称；
- 手动配置 [/config](config) 中的软件自定义设置；

## 软件配置

```Shell
# Install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# espanso
ln -s Dotfiles/.config/espanso /Users/alex/Library/Preferences/espanso

# npm
asdf install nodejs lts
xargs npm install --global < $HOME/Dotfiles/config/npm/npm.txt

# pipx
xargs pipx install < $HOME/Dotfiles/config/pipx/npm.txt
```
