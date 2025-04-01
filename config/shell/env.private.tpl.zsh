export HF_TOKEN="op://dev-self/Hugging Face/macos/HF_TOKEN"
export LOGFIRE_TOKEN="op://dev-self/Logfire/prototypes/LOGFIRE_TOKEN"

export ANTHROPIC_API_KEY="op://prod-coach/Anthropic/macos/ANTHROPIC_API_KEY"
export GEMINI_API_KEY="op://dev-self/Vertex Al/macos/GEMINI_API_KEY"
export OPENAI_API_KEY="op://dev-self/OpenAI Platform/macos/OPENAI_API_KEY"

export LLM_GEMINI_KEY=$GEMINI_API_KEY

set-rclone-env() {
  export RCLONE_CONFIG_R2_TYPE=s3
  export RCLONE_CONFIG_R2_PROVIDER=Cloudflare
  export RCLONE_CONFIG_R2_ENDPOINT="op://dev-self/Cloudflare/credentials/ENDPOINT"
  export RCLONE_CONFIG_R2_ACCESS_KEY_ID="op://dev-self/Cloudflare/credentials/ACCESS_KEY_ID"
  export RCLONE_CONFIG_R2_SECRET_ACCESS_KEY="op://dev-self/Cloudflare/credentials/SECRET_ACCESS_KEY"

  export RCLONE_CONFIG_TIGRIS_TYPE=s3
  export RCLONE_CONFIG_TIGRIS_PROVIDER=AWS
  export RCLONE_CONFIG_TIGRIS_ENDPOINT="op://dev-self/Tigris/credentials/ENDPOINT"
  export RCLONE_CONFIG_TIGRIS_ACCESS_KEY_ID="op://dev-self/Tigris/credentials/ACCESS_KEY_ID"
  export RCLONE_CONFIG_TIGRIS_SECRET_ACCESS_KEY="op://dev-self/Tigris/credentials/SECRET_ACCESS_KEY"

  export RCLONE_CONFIG_HETZNER_TYPE=s3
  export RCLONE_CONFIG_HETZNER_PROVIDER=AWS
  export RCLONE_CONFIG_HETZNER_ENDPOINT="op://dev-self/Hetzner/credentials/ENDPOINT"
  export RCLONE_CONFIG_HETZNER_ACCESS_KEY_ID="op://dev-self/Hetzner/credentials/ACCESS_KEY_ID"
  export RCLONE_CONFIG_HETZNER_SECRET_ACCESS_KEY="op://dev-self/Hetzner/credentials/SECRET_ACCESS_KEY"
}

set-tigris-env() {
  export AWS_ENDPOINT_URL=https://fly.storage.tigris.dev
  export AWS_ENDPOINT_URL_S3=https://fly.storage.tigris.dev
  export AWS_ENDPOINT_URL_IAM=https://fly.iam.storage.tigris.dev
  export AWS_REGION=auto
  export AWS_ACCESS_KEY_ID="op://dev-self/Tigris/credentials/access_key_id"
  export AWS_SECRET_ACCESS_KEY="op://dev-self/Tigris/credentials/secret_access_key"
}

set-bedrock-env() {
  export ANTHROPIC_MODEL="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
  export AWS_ACCESS_KEY_ID="op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID"
  export AWS_SECRET_ACCESS_KEY="op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY"
  export CLAUDE_CODE_USE_BEDROCK=1
  export DISABLE_PROMPT_CACHING=1
}
