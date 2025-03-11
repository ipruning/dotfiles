set -x HF_TOKEN "op://dev-self/Hugging Face/macos/HF_TOKEN"
set -x LOGFIRE_TOKEN "op://dev-self/426cvuij6hhwgrmghdzue2p5hu/macos/LOGFIRE_TOKEN"

set -x GEMINI_API_KEY "op://dev-self/Vertex Al/macos/GEMINI_API_KEY"
set -x OPENAI_API_KEY "op://dev-self/OpenAI Platform/macos/OPENAI_API_KEY"
set -x OPENAI_BASE_URL "https://api.openai.com/v1"

set -x AI_PY_API_KEY $OPENAI_API_KEY
set -x LLM_GEMINI_KEY $GEMINI_API_KEY
set -x DEEPSEEK_API_KEY "op://dev-self/DeepSeek/credentials/DEEPSEEK_API_KEY"
set -x DEEPSEEK_BASE_URL "op://dev-self/DeepSeek/credentials/DEEPSEEK_BASE_URL"

set -x ROAM_RESEARCH_TOKEN "op://dev-self/Roam Research/credentials/ROAM_RESEARCH_TOKEN"
set -x ROAM_RESEARCH_ENDPOINT "op://dev-self/Roam Research/credentials/ROAM_RESEARCH_ENDPOINT"

function set-rclone-env
    set -x RCLONE_CONFIG_R2_TYPE "s3"
    set -x RCLONE_CONFIG_R2_PROVIDER "Cloudflare"
    set -x RCLONE_CONFIG_R2_ENDPOINT "op://dev-self/Cloudflare/credentials/ENDPOINT"
    set -x RCLONE_CONFIG_R2_ACCESS_KEY_ID "op://dev-self/Cloudflare/credentials/ACCESS_KEY_ID"
    set -x RCLONE_CONFIG_R2_SECRET_ACCESS_KEY "op://dev-self/Cloudflare/credentials/SECRET_ACCESS_KEY"

    set -x RCLONE_CONFIG_TIGRIS_TYPE "s3"
    set -x RCLONE_CONFIG_TIGRIS_PROVIDER "AWS"
    set -x RCLONE_CONFIG_TIGRIS_ENDPOINT "op://dev-self/Tigris/credentials/ENDPOINT"
    set -x RCLONE_CONFIG_TIGRIS_ACCESS_KEY_ID "op://dev-self/Tigris/credentials/ACCESS_KEY_ID"
    set -x RCLONE_CONFIG_TIGRIS_SECRET_ACCESS_KEY "op://dev-self/Tigris/credentials/SECRET_ACCESS_KEY"
end

function set-tigris-env
    set -x AWS_ENDPOINT_URL "https://fly.storage.tigris.dev"
    set -x AWS_ENDPOINT_URL_S3 "https://fly.storage.tigris.dev"
    set -x AWS_ENDPOINT_URL_IAM "https://fly.iam.storage.tigris.dev"
    set -x AWS_REGION "auto"
    set -x AWS_ACCESS_KEY_ID "op://dev-self/Tigris/credentials/access_key_id"
    set -x AWS_SECRET_ACCESS_KEY "op://dev-self/Tigris/credentials/secret_access_key"
end

function set-bedrock-env
    set -x ANTHROPIC_MODEL "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
    set -x AWS_ACCESS_KEY_ID "op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID"
    set -x AWS_SECRET_ACCESS_KEY "op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY"
    set -x CLAUDE_CODE_USE_BEDROCK 1
    set -x DISABLE_PROMPT_CACHING 1
end
