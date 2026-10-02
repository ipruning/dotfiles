"""Declared shell generators and pinned runtime assets."""

from .runtime_models import ShellInitSpec

FUNCTION_SPECS = (
    ShellInitSpec("mise", "mise", "zsh", ("mise", "activate", "zsh"), "_mise.zsh"),
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
        ("starship", "init", "bash"),
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
    ("bootdev", "bootdev", ("bootdev", "completion", "zsh"), "_bootdev", ()),
    ("ov", "ov", ("ov", "--completion", "zsh"), "_ov", ()),
    ("just", "just", ("just", "--completions", "zsh"), "_just", ()),
    ("codex", "codex", ("codex", "completion", "zsh"), "_codex", ()),
    ("jj", "jj", ("jj", "util", "completion", "zsh"), "_jj", ()),
    ("linear", "linear", ("linear", "completions", "zsh"), "_linear", ()),
    ("sesh", "sesh", ("sesh", "completion", "zsh"), "_sesh", ()),
    ("op", "op", ("op", "completion", "zsh"), "_op", ()),
    # Keep the resolver inputs exact: this generator is an explicit runtime
    # refresh boundary, not a request to execute the latest PyPI release.
    (
        "llm",
        "uvx",
        ("uvx", "--with", "httpx==0.28.1", "llm==0.33"),
        "_llm",
        (("_LLM_COMPLETE", "zsh_source"),),
    ),
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
        "3d574ccf48804b10dca52625df13da5edae7f553",
        "fast-syntax-highlighting.plugin.zsh",
    ),
)

WASM_SPECS = (
    (
        "zellij-sessionizer",
        "https://github.com/laperlej/zellij-sessionizer/releases/download/v0.5.0/zellij-sessionizer.wasm",
        "c41841c023e74e81f99a0fd8d95e0504ed202df2cdb92604df51c9e4ea0ba05b",
    ),
    (
        "zjstatus",
        "https://github.com/dj95/zjstatus/releases/download/v0.23.0/zjstatus.wasm",
        "e006901223524239db618021e4cc5d17f82dc4bfae5432895ba41f03f13861ff",
    ),
)

OWNED_GENERATED_DIRECTORIES = ("functions", "completions", "plugins")
