"""Declared shell generators and pinned plugin assets."""

from .generate_models import ShellInitSpec

FUNCTION_SPECS = (
    ShellInitSpec(
        "starship", "starship", "zsh", ("starship", "init", "zsh"), "_starship.zsh"
    ),
    ShellInitSpec(
        "atuin",
        "atuin",
        "zsh",
        ("atuin", "init", "zsh", "--disable-up-arrow"),
        "_atuin.zsh",
    ),
    ShellInitSpec(
        "zoxide",
        "zoxide",
        "zsh",
        ("zoxide", "init", "zsh", "--cmd", "j"),
        "_zoxide.zsh",
    ),
    ShellInitSpec("tv", "tv", "zsh", ("tv", "init", "zsh"), "_tv.zsh"),
    ShellInitSpec(
        "try-rs",
        "try-rs",
        "zsh",
        ("try-rs", "--setup-stdout", "zsh"),
        "_try-rs.zsh",
    ),
    ShellInitSpec(
        "starship-bash",
        "starship",
        "bash",
        ("starship", "init", "bash", "--print-full-init"),
        "_starship.bash",
    ),
    ShellInitSpec(
        "atuin-bash",
        "atuin",
        "bash",
        ("atuin", "init", "bash", "--disable-up-arrow"),
        "_atuin.bash",
    ),
    ShellInitSpec(
        "zoxide-bash",
        "zoxide",
        "bash",
        ("zoxide", "init", "bash", "--cmd", "j"),
        "_zoxide.bash",
    ),
    ShellInitSpec(
        "mise-bash", "mise", "bash", ("mise", "activate", "bash"), "_mise.bash"
    ),
    ShellInitSpec("mise-nu", "mise", "nu", ("mise", "activate", "nu"), "_mise.nu"),
    ShellInitSpec(
        "zoxide-nu",
        "zoxide",
        "nu",
        ("zoxide", "init", "nushell"),
        "_zoxide.nu",
    ),
)

COMPLETION_SPECS = (
    ("codex", "codex", ("codex", "completion", "zsh"), "_codex", ()),
    ("hunk", "hunk", ("hunk", "completion", "zsh"), "_hunk", ()),
    ("lazygit", "lazygit", ("lazygit", "completion", "zsh"), "_lazygit", ()),
    ("linear", "linear", ("linear", "completions", "zsh"), "_linear", ()),
    ("mise", "mise", ("mise", "completion", "zsh"), "_mise", ()),
    ("op", "op", ("op", "completion", "zsh"), "_op", ()),
    ("rumdl", "rumdl", ("rumdl", "completions", "zsh"), "_rumdl", ()),
    ("uv", "uv", ("uv", "generate-shell-completion", "zsh"), "_uv", ()),
)

PLUGIN_SPECS = (
    (
        "fzf-tab",
        "https://github.com/Aloxaf/fzf-tab",
        "24105b15714bfec37989ed5c5b6e60f572253019",
        "fzf-tab.plugin.zsh",
    ),
    (
        "zsh-autosuggestions",
        "https://github.com/zsh-users/zsh-autosuggestions",
        "85919cd1ffa7d2d5412f6d3fe437ebdbeeec4fc5",
        "zsh-autosuggestions.zsh",
    ),
    (
        "fast-syntax-highlighting",
        "https://github.com/zdharma-continuum/fast-syntax-highlighting",
        "4672ad5dd9ad68a7effc1476d65afb7c584ce2b3",
        "fast-syntax-highlighting.plugin.zsh",
    ),
)

OWNED_GENERATED_DIRECTORIES = ("functions", "completions", "plugins")
