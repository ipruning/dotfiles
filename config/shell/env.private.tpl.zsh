export AMP_API_KEY="op://dev/Amp/AMP_API_KEY"
export ANTHROPIC_API_KEY="op://dev/Anthropic/macos/ANTHROPIC_API_KEY"
export EXA_API_KEY="op://Private/Exa/macos/EXA_API_KEY"
export GEMINI_API_KEY="op://dev/Vertex Al/macos/GEMINI_API_KEY"
export HF_TOKEN="op://dev/Hugging Face/macos/HF_TOKEN"
export LLM_GEMINI_KEY="op://dev/Vertex Al/macos/GEMINI_API_KEY"
export OPENAI_API_KEY="op://dev-work/OpenAI Platform/macos/OPENAI_API_KEY"

claude() {
  env AWS_ACCESS_KEY_ID="op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY" \
      ANTHROPIC_MODEL="us.anthropic.claude-opus-4-1-20250805-v1:0" \
      ANTHROPIC_SMALL_FAST_MODEL="us.anthropic.claude-3-5-haiku-20241022-v1:0" \
      AWS_REGION="us-east-1" \
      CLAUDE_CODE_USE_BEDROCK=1 \
      claude "$@"
}

claude-sonnet() {
  env AWS_ACCESS_KEY_ID="op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY" \
      ANTHROPIC_MODEL="us.anthropic.claude-sonnet-4-20250514-v1:0" \
      ANTHROPIC_SMALL_FAST_MODEL="us.anthropic.claude-3-5-haiku-20241022-v1:0" \
      AWS_REGION="us-west-2" \
      CLAUDE_CODE_USE_BEDROCK=1 \
      claude "$@"
}
