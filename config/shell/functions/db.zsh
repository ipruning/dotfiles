typeset -A db_commands=(
  csv-schema 'csv-schema'
  csv-to-parquet 'csv-to-parquet'
  json-schema 'json-schema'
  json-sqlite 'json-sqlite'
  sqlite-query 'sqlite-query'
  sqlite-schema 'sqlite-schema'
)

function csv-to-parquet() {
  file_path="$1"
  duckdb -c "COPY (SELECT * FROM read_csv_auto('$file_path')) TO '${file_path%.*}.parquet' (FORMAT PARQUET);"
}

function csv-schema() {
  file_path="$1"
  duckdb -c "CREATE TEMP TABLE temp_csv_dump AS SELECT * FROM read_csv_auto('$file_path'); SELECT * FROM PRAGMA_TABLE_INFO('temp_csv_dump');"
}

function json-schema() {
  file_path="$1"
  duckdb -c "CREATE TEMP TABLE temp_json_dump AS SELECT * FROM read_json_auto('$file_path'); SELECT * FROM PRAGMA_TABLE_INFO('temp_json_dump');"
}

function sqlite-schema() {
  db_path="$1"
  sqlite3 "$db_path" '.schema'
}

function sqlite-query() {
  db_path="$1"
  shift
  sqlite3 "$db_path" "$@"
}

function db() {
  if [[ $# -eq 0 ]]; then
    echo "Usage: db [subcommand]"
    for key desc in ${(kv)db_commands}; do
      printf "  %-3s = %s\n" "$key" "$desc"
    done
    return
  else
    local cmd=$1
    if (( ${+db_commands[$cmd]} )); then
      shift
      local command=(${=db_commands[$cmd]})
      "$command[@]" "$@"
    else
      echo "Unknown command: $cmd"
      return 1
    fi
  fi
}

compdef _db db

function _db() {
  local -a subcommands
  for key desc in ${(kv)db_commands}; do
    subcommands+=("$key:${(q)desc}")
  done

  if (( CURRENT == 2 )); then
    _describe -t commands 'db subcommands' subcommands
  fi
}
