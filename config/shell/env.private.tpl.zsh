export HF_TOKEN="op://dev/Hugging Face/macos/HF_TOKEN"

# export ANTHROPIC_API_KEY="op://dev/Anthropic/macos/ANTHROPIC_API_KEY"
export GEMINI_API_KEY="op://dev/Vertex Al/macos/GEMINI_API_KEY"
# export OPENAI_API_KEY="op://dev/OpenAI Platform/macos/OPENAI_API_KEY"

export LLM_GEMINI_KEY=$GEMINI_API_KEY

set-aws-bedrock-dev-work() {
  export ANTHROPIC_MODEL="us.anthropic.claude-3-7-sonnet-20250219-v1:0"
  export AWS_ACCESS_KEY_ID="op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID"
  export AWS_SECRET_ACCESS_KEY="op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY"
  export CLAUDE_CODE_USE_BEDROCK=1
}

# export ZED_ACCESS_KEY_ID="op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID"
# export ZED_SECRET_ACCESS_KEY="op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY"
# export ZED_AWS_REGION="us-west-2"
