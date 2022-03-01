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
# install Homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# install Homebrew packages
brew bundle --file=$HOME/dotfiles/config/brew/Brewfile

# install AutoCorrrect
curl -sSL https://git.io/JcGER | bash

# install npm packages
asdf install nodejs lts
asdf global nodejs lts
xargs npm install --global < $HOME/dotfiles/config/npm/npm.txt

# install pipx packages
xargs pipx install < $HOME/dotfiles/config/pipx/npm.txt
```

```Shell
# init
git clone https://github.com/Spehhhhh/dotfiles.git $HOME/dotfiles

# espanso
ln -s $HOME/dotfiles/.config/espanso $HOME/Library/Preferences/espanso
```
