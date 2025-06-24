export HF_TOKEN="op://dev/Hugging Face/macos/HF_TOKEN"

export AMP_API_KEY="op://dev/Amp/AMP_API_KEY"
export ANTHROPIC_API_KEY="op://dev/Anthropic/macos/ANTHROPIC_API_KEY"
export GEMINI_API_KEY="op://dev/Vertex Al/macos/GEMINI_API_KEY"
export LLM_GEMINI_KEY=$GEMINI_API_KEY
export OPENAI_API_KEY="op://dev-work/OpenAI Platform/macos/OPENAI_API_KEY"

setup-claude-code() {
  export AWS_ACCESS_KEY_ID="op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID"
  export AWS_SECRET_ACCESS_KEY="op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY"
  export ANTHROPIC_MODEL="us.anthropic.claude-sonnet-4-20250514-v1:0"
  export ANTHROPIC_SMALL_FAST_MODEL="us.anthropic.claude-3-5-haiku-20241022-v1:0"
  export AWS_REGION="us-west-2"
  export CLAUDE_CODE_USE_BEDROCK=1
}

alias claude="setup-claude-code && claude"
