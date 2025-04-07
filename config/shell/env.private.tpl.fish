set -gx HF_TOKEN "op://dev/Hugging Face/macos/HF_TOKEN"

set -gx ANTHROPIC_API_KEY "op://dev/Anthropic/macos/ANTHROPIC_API_KEY"
set -gx GEMINI_API_KEY "op://dev/Vertex Al/macos/GEMINI_API_KEY"
set -gx OPENAI_API_KEY "op://dev/OpenAI Platform/macos/OPENAI_API_KEY"

set -gx LLM_GEMINI_KEY $GEMINI_API_KEY

function set-aws-bedrock-dev-work
  set -gx ANTHROPIC_MODEL "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
  set -gx AWS_ACCESS_KEY_ID "op://dev-work/AWS/claude_code/AWS_ACCESS_KEY_ID"
  set -gx AWS_SECRET_ACCESS_KEY "op://dev-work/AWS/claude_code/AWS_SECRET_ACCESS_KEY"
  set -gx CLAUDE_CODE_USE_BEDROCK 1
  set -gx DISABLE_PROMPT_CACHING 1
end
