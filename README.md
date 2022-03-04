# My dotfiles

- [My dotfiles](#my-dotfiles)
  - [TODO](#todo)
  - [Bootstrap](#bootstrap)
  - [Customize](#customize)
    - [`zshrc`](#zshrc)
    - [`~/.gitconfig.local`](#gitconfiglocal)
    - [macOS](#macos)
    - [Arch](#arch)
  - [ChangeLog](#changelog)

## TODO

- [ ] 重构脚本使其尽可能幂等；
- [ ] 添加配图；

## Bootstrap

> ⚠️ 如果你不完全理解这个脚本的作用，就不要运行它！
> ⚠️ If you don't fully understand what this script does, don't run it!

Execute the bootstrap script（执行 bootstrap 脚本）

```shell
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Spehhhhh/dotfiles/master/bootstrap.sh)"
```

If you are a macOS user, you will need to install xcode first or download it here  <https://developer.apple.com/download/more/>.

```shell
xcode-select --install
```

In addition, you will need to sign into the AppStore with your Apple ID as the MAS app is available in the Brewfile.

脚本会执行以下步骤：

1. 将仓库 Clone 至 `$HOME/dotfiles`，如果本地不存在的话；
2. TODO

## Customize

### `zshrc`

### `~/.gitconfig.local`

使用 `~/.gitconfig.local` 来存储敏感信息，如用户名，邮箱，私钥等。

### macOS

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

### Arch

## ChangeLog

- 220301 Make the repo public
