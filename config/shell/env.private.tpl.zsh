export HF_TOKEN="op://dev/Hugging Face/macos/HF_TOKEN"

export AMP_API_KEY="op://dev/Amp/AMP_API_KEY"
export ANTHROPIC_API_KEY="op://dev/Anthropic/macos/ANTHROPIC_API_KEY"
export GEMINI_API_KEY="op://dev/Vertex Al/macos/GEMINI_API_KEY"
export LLM_GEMINI_KEY=$GEMINI_API_KEY
export OPENAI_API_KEY="op://dev-work/OpenAI Platform/macos/OPENAI_API_KEY"

claude() {
  env AWS_ACCESS_KEY_ID="op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID" \
      AWS_SECRET_ACCESS_KEY="op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY" \
      ANTHROPIC_MODEL="op://dev-work/Anthropic/macos/ANTHROPIC_MODEL" \
      ANTHROPIC_SMALL_FAST_MODEL="op://dev-work/Anthropic/macos/ANTHROPIC_SMALL_FAST_MODEL" \
      AWS_REGION="op://dev-work/AWS/claude_code/AWS_REGION" \
      CLAUDE_CODE_USE_BEDROCK=1 \
      claude "$@"
}
