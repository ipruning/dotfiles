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

```shell
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Spehhhhh/dotfiles/master/bootstrap.sh)"
```

脚本会执行以下步骤：

1. 将仓库 Clone 至 `$HOME/dotfiles`，如果本地不存在的话；

## Customize

### `zshrc`

### `~/.gitconfig.local`

使用 `~/.gitconfig.local` 来存储敏感信息，如用户名，邮箱，私钥等。

### macOS

- 修改用户名；
- 修改共享电脑名称；
- 启用触摸板轻触；
- 启用三指拖移；
- 关闭自动重新排列空间；
- 启用 Tab 键移动焦点；
- 修改共享电脑名称；

### Arch

## ChangeLog

- 220301 Make the repo public
