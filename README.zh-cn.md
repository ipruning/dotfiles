# My dotfiles

<!--rehype:style=font-size: 38px; border-bottom: 0; display: flex; min-height: 260px; align-items: center; justify-content: center;-->

[![jaywcjlove/sb](https://wangchujiang.com/sb/lang/english.svg)](README.md) [![jaywcjlove/sb](https://wangchujiang.com/sb/lang/chinese.svg)](README.zh-cn.md)

<!--rehype:style=text-align: center;-->

## Table of Contents

- [Table of Contents](#table-of-contents)
- [TODO](#todo)
- [Bootstrap](#bootstrap)
- [Customize](#customize)
    - [`zshrc`](#zshrc)
    - [`~/.gitconfig.local`](#gitconfiglocal)
    - [macOS 配置](#macos-配置)
    - [macOS Homebrew 配置指南](#macos-homebrew-配置指南)
    - [Arch Linux 配置](#arch-linux-配置)
- [ChangeLog](#changelog)

## TODO

- [ ] 重构脚本使其尽可能幂等；
- [ ] 为 bootstrap 添加 Homebrew 镜像；并提供一个选项；
- [ ] 添加配图；

## Bootstrap

> ⚠️ 如果你不完全理解这个脚本的作用，就不要运行它！

执行 bootstrap 脚本。

```shell
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Spehhhhh/dotfiles/master/bootstrap.sh)"
```

如果是 macOS 新用户，可能需要安装 XCode Command Line Tools。

```shell
xcode-select --install
```

此外，你需要用你的 Apple ID 登录 App Store，因为 Brewfile 中的 NAS 程序必须经过验证。

脚本会执行以下步骤：

1. 将仓库 Clone 至 `$HOME/dotfiles`，如果本地不存在的话；
2. TODO

## Customize

### `zshrc`

### `~/.gitconfig.local`

使用 `~/.gitconfig.local` 来存储敏感信息，如用户名，邮箱，私钥等。

### macOS 配置

- 修改用户名；
- 修改共享电脑名称 `sudo scutil --set HostName mac`；
- 启用触摸板轻触；
- 辅助功能 - 指针控制（或鼠标与触控板）- 触控板选项：启动拖移 (三指拖移)；
- 关闭自动重新排列空间；
- 启用 Tab 键移动焦点；
- 修改共享电脑名称；
- 设置触发角；
- Dock
    - 添加空白格： `defaults write com.apple.dock persistent-apps -array-add '{"tile-type"="spacer-tile";}'; Killall Dock`
- Finder
    - 显示拓展名；
    - 标题栏显示完整路径；
    - 显示隐藏文件；

### macOS Homebrew 配置指南

如果你不能 🔬 🧗‍♀️ 则建议使用清华大学提供的 Homebrew 镜像，具体请参考[清华大学开源软件镜像站](https://mirrors.tuna.tsinghua.edu.cn/help/homebrew/)。

```shell
# 把默认 Shell 从 Bash 改为 ZSH。
chsh -s $(which zsh)

# 暂时关闭 SSL 证书验证。之后请手动开启。
git config --global http.sslVerify "false"

# 配置清华镜像环境变量
export HOMEBREW_BREW_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/brew.git"
export HOMEBREW_CORE_GIT_REMOTE="https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/homebrew-core.git"
export HOMEBREW_BOTTLE_DOMAIN="https://mirrors.tuna.tsinghua.edu.cn/homebrew-bottles"

# 使用清华镜像的安装脚本安装 Homebrew
git clone --depth=1 https://mirrors.tuna.tsinghua.edu.cn/git/homebrew/install.git brew-install
/bin/bash brew-install/install.sh

# 删除安装时产生的临时文件
rm -rf brew-install

# 安装成功后需将 Homebrew 的相关路径加入到环境变量中。如何添加环境变量请参考 Homebrew 命令行输出。
```

### Arch Linux 配置

## ChangeLog

- 2022-05-25 Update REAMDE
- 2022-03-01 Make the repo public
