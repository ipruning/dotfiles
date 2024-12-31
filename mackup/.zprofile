if [[ $OSTYPE = darwin* ]]; then
  if [ -d "/opt/homebrew/bin" ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
fi
