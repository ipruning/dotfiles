# 我的 dotfiles

<!--rehype:style=font-size: 38px; border-bottom: 0; display: flex; min-height: 260px; align-items: center; justify-content: center;-->

[![jaywcjlove/sb](https://wangchujiang.com/sb/lang/english.svg)](README.md) [![jaywcjlove/sb](https://wangchujiang.com/sb/lang/chinese.svg)](README.zh-cn.md)

<!--rehype:style=text-align: center;-->

个人 macOS 开发环境配置文件，支持 zsh/fish 双 shell 环境和现代化工具链。

## 特性

- 🐚 **双 shell 支持**：zsh 和 fish 配置，包含现代插件
- 🛠️ **工具管理**：使用 mise 进行统一版本和工具管理
- 📦 **包管理**：Homebrew 与机器特定包列表（M2/M4）
- ⚡ **现代 CLI 工具**：eza、bat、fd、fzf、lazygit、yazi、zellij
- 🎨 **一致的主题**：Starship 提示符配合 catppuccin-mocha 主题
- 🔧 **预提交钩子**：自动化 linting、安全扫描和中日韩文本格式化
- 📱 **macOS 应用**：Aerospace、Karabiner、Ghostty、Zed、Linear Mouse
- 🔍 **增强生产力**：atuin 用于 shell 历史记录，television 用于文件浏览

## 安装

1. 克隆仓库：

   ```bash
   git clone https://github.com/ipruning/dotfiles.git ~/dotfiles
   ```

2. 使用 mise 安装依赖：

   ```bash
   mise install
   ```

3. 设置预提交钩子：

   ```bash
   pre-commit install
   ```

4. 加载 shell 配置：

   ```bash
   # 对于 zsh
   source ~/.zshrc

   # 对于 fish
   source ~/.config/fish/config.fish
   ```

## 目录结构

- `config/` - 按类别组织的配置文件
  - `shell/` - Shell 配置（别名、环境变量、函数、插件）
  - `packages/` - 不同机器的 Homebrew 包列表（M2/M4）
  - `misc/` - 额外配置文件（surfingkeys.js）
  - `mackup/` - Mackup 应用设置备份配置
- `home/` - 家目录文件和 XDG 配置
  - `.config/` - 遵循 XDG 标准的应用程序配置
    - `aerospace/` - 窗口管理
    - `atuin/` - Shell 历史同步
    - `bat/` - 语法高亮主题
    - `fish/` - Fish shell 配置
    - `gh/` - GitHub CLI
    - `karabiner/` - 键盘映射
    - `mise/` - 工具版本管理
    - `television/` - 文件浏览器主题
    - `yazi/` - 终端文件管理器
    - `zed/` - 代码编辑器设置
    - `zellij/` - 终端复用器布局

## 工具和应用

### CLI 工具（通过 mise 管理）

- **编程语言**：Node.js、Python、Go、Rust、Ruby、Deno、Bun
- **开发工具**：pre-commit、shellcheck、各种 linter（biome、ruff、typos-cli）
- **安全工具**：ripsecrets、lychee、cosign、slsa-verifier
- **生产力工具**：lazygit、atuin、fzf、just、gfold
- **AI/ML**：claude-code、amp、llm、modal、codex
- **构建工具**：cargo-binstall、xh、tea、kamal

### macOS 应用程序

- **窗口管理**：Aerospace（平铺窗口管理器）
- **键盘映射**：Karabiner Elements（按键重映射）
- **鼠标控制**：Linear Mouse（加速和滚动）
- **终端**：Ghostty（现代终端模拟器）
- **编辑器**：Zed（协作代码编辑器）
- **终端复用器**：Zellij（现代 tmux 替代品）
- **文件管理器**：Yazi（终端文件管理器）
- **版本控制**：Lazygit（终端 Git UI）

## 自定义配置

### 私有配置

使用 `.tpl` 模板文件创建私有配置：

- `config/shell/env.private.tpl.zsh` → `config/shell/env.private.zsh`
- `config/shell/env.private.tpl.fish` → `config/shell/env.private.fish`

### 机器特定包

为不同机器类型维护包列表：

- `config/packages/brew_dump.M2.txt` - M2 Mac 完整包列表
- `config/packages/brew_dump.M4.txt` - M4 Mac 完整包列表
- `config/packages/brew_leaves.M*.txt` - 明确安装的包
- `config/packages/brew_installed.M*.txt` - 所有已安装的包

## 主要特性与亮点

### Shell 增强

- **zsh 插件**：fast-syntax-highlighting、zsh-autosuggestions、zsh-autocomplete、fzf-tab
- **现代别名**：`ls` → `eza`、`cat` → `bat`、`find` → `fd`、`grep` → `rg`
- **智能导航**：zoxide 用于智能目录跳转
- **历史同步**：atuin 用于跨设备 shell 历史

### 安全与质量

- **预提交钩子**：YAML 验证、尾部空白移除、中日韩文本格式化
- **秘密扫描**：ripsecrets 防止凭据泄露
- **链接检查**：lychee 检测无效链接
- **代码质量**：多种 linter（biome、ruff、typos-cli）自动修复

### 开发工作流

- **Git 集成**：lazygit、ugit 增强版本控制
- **终端复用**：Zellij 配合自定义布局和插件
- **文件管理**：Yazi 支持预览和现代导航
- **代码编辑**：Zed 集成终端工具任务

## 更新日志

- 2025-06-24 更新 README，包含最新工具、结构和详细文档
- 2025-06-23 完全重写 README，添加详细文档
- 2022-05-25 更新 README
- 2022-03-01 公开仓库
