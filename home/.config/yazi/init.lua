require("starship"):setup()

require("relative-motions"):setup({
    show_numbers = "relative",
    show_motion = true,
    enter_mode = "first"
})

require("duckdb"):setup({
    mode = "standard",
    row_id = true,
    minmax_column_width = 30
})
