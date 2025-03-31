set -x HF_TOKEN "op://dev-self/Hugging Face/macos/HF_TOKEN"
set -x LOGFIRE_TOKEN "op://dev-self/Logfire/prototypes/LOGFIRE_TOKEN"

set -x ANTHROPIC_API_KEY "op://prod-coach/Anthropic/macos/ANTHROPIC_API_KEY"
set -x GEMINI_API_KEY "op://dev-self/Vertex Al/macos/GEMINI_API_KEY"
set -x OPENAI_API_KEY "op://dev-self/OpenAI Platform/macos/OPENAI_API_KEY"

set -x LLM_GEMINI_KEY $GEMINI_API_KEY

function set-rclone-env
  set -gx RCLONE_CONFIG_R2_TYPE "s3"
  set -gx RCLONE_CONFIG_R2_PROVIDER "Cloudflare"
  set -gx RCLONE_CONFIG_R2_ENDPOINT "op://dev-self/Cloudflare/credentials/ENDPOINT"
  set -gx RCLONE_CONFIG_R2_ACCESS_KEY_ID "op://dev-self/Cloudflare/credentials/ACCESS_KEY_ID"
  set -gx RCLONE_CONFIG_R2_SECRET_ACCESS_KEY "op://dev-self/Cloudflare/credentials/SECRET_ACCESS_KEY"

  set -gx RCLONE_CONFIG_TIGRIS_TYPE "s3"
  set -gx RCLONE_CONFIG_TIGRIS_PROVIDER "AWS"
  set -gx RCLONE_CONFIG_TIGRIS_ENDPOINT "op://dev-self/Tigris/credentials/ENDPOINT"
  set -gx RCLONE_CONFIG_TIGRIS_ACCESS_KEY_ID "op://dev-self/Tigris/credentials/ACCESS_KEY_ID"
  set -gx RCLONE_CONFIG_TIGRIS_SECRET_ACCESS_KEY "op://dev-self/Tigris/credentials/SECRET_ACCESS_KEY"

  set -gx RCLONE_CONFIG_HETZNER_TYPE "s3"
  set -gx RCLONE_CONFIG_HETZNER_PROVIDER "AWS"
  set -gx RCLONE_CONFIG_HETZNER_ENDPOINT "op://dev-self/Hetzner/credentials/ENDPOINT"
  set -gx RCLONE_CONFIG_HETZNER_ACCESS_KEY_ID "op://dev-self/Hetzner/credentials/ACCESS_KEY_ID"
  set -gx RCLONE_CONFIG_HETZNER_SECRET_ACCESS_KEY "op://dev-self/Hetzner/credentials/SECRET_ACCESS_KEY"
end

function set-tigris-env
  set -gx AWS_ENDPOINT_URL "https://fly.storage.tigris.dev"
  set -gx AWS_ENDPOINT_URL_S3 "https://fly.storage.tigris.dev"
  set -gx AWS_ENDPOINT_URL_IAM "https://fly.iam.storage.tigris.dev"
  set -gx AWS_REGION "auto"
  set -gx AWS_ACCESS_KEY_ID "op://dev-self/Tigris/credentials/access_key_id"
  set -gx AWS_SECRET_ACCESS_KEY "op://dev-self/Tigris/credentials/secret_access_key"
end

function set-bedrock-env
  set -gx ANTHROPIC_MODEL "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
  set -gx AWS_ACCESS_KEY_ID "op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID"
  set -gx AWS_SECRET_ACCESS_KEY "op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY"
  set -gx CLAUDE_CODE_USE_BEDROCK 1
  set -gx DISABLE_PROMPT_CACHING 1
end
