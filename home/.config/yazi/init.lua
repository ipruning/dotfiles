require("full-border"):setup {
    type = ui.Border.ROUNDED,
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

-- require("relative-motions"):setup({
--     show_numbers = "relative",
-- })
