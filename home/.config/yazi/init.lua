require("starship"):setup()

require("duckdb"):setup({
    mode = "standard",
    row_id = true,
    minmax_column_width = 30
})
