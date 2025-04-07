require("full-border"):setup {
    ---@diagnostic disable-next-line: undefined-global
    type = ui.Border.ROUNDED,
}

require("starship"):setup()

require("duckdb"):setup({
    mode = "standard",
    row_id = true,
    minmax_column_width = 30
})

require("relative-motions"):setup({
    show_numbers = "relative",
    show_motion = true,
    enter_mode = "first",
})
