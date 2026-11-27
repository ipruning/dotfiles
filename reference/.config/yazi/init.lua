require("full-border"):setup {
    set = "rounded",
}

require("starship"):setup()

require("git"):setup {
	order = 1500,
}

require("duckdb"):setup({
    mode = "standard",
    row_id = true,
    minmax_column_width = 30
})
