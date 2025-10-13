export HF_TOKEN="op://dev/Hugging Face/macos/HF_TOKEN"

tigrisfs() {
  env AWS_ACCESS_KEY_ID="op://dev/Tigris/alex-macbook-tigrisfs/ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="op://dev/Tigris/alex-macbook-tigrisfs/SECRET_ACCESS_KEY" \
      AWS_ENDPOINT_URL_S3="https://t3.storage.dev" \
      AWS_ENDPOINT_URL_IAM="https://iam.storage.dev" \
      AWS_REGION="auto" \
      command tigrisfs "$@"
}
