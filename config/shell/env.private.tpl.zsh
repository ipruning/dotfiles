export HF_TOKEN="op://dev/Hugging Face/macos/HF_TOKEN"

claude() {
  env AWS_ACCESS_KEY_ID="op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY" \
      ANTHROPIC_DEFAULT_HAIKU_MODEL="us.anthropic.claude-3-5-haiku-20241022-v1:0" \
      ANTHROPIC_DEFAULT_OPUS_MODEL="us.anthropic.claude-opus-4-1-20250805-v1:0" \
      ANTHROPIC_DEFAULT_SONNET_MODEL="us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
      ANTHROPIC_MODEL="us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
      AWS_REGION="us-west-2" \
      CLAUDE_CODE_SUBAGENT_MODEL="us.anthropic.claude-sonnet-4-5-20250929-v1:0" \
      CLAUDE_CODE_USE_BEDROCK=1 \
      claude "$@"
}

tigrisfs() {
  env AWS_ACCESS_KEY_ID="op://dev/Tigris/alex-macbook-tigrisfs/ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="op://dev/Tigris/alex-macbook-tigrisfs/SECRET_ACCESS_KEY" \
      AWS_ENDPOINT_URL_S3="https://t3.storage.dev" \
      AWS_ENDPOINT_URL_IAM="https://iam.storage.dev" \
      AWS_REGION="auto" \
      tigrisfs "$@"
}
