function csv-to-parquet() {
  file_path="$1"
  duckdb -c "COPY (SELECT * FROM read_csv_auto('$file_path')) TO '${file_path%.*}.parquet' (FORMAT PARQUET);"
}
