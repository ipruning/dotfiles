#!/usr/bin/env bash
#MISE description="Initialize Monorepo CI/CD tools"
#MISE env={MISE_DEBUG=1,MISE_LOG_HTTP=1,MISE_RAW=1,MISE_JOBS=1}

cd "$(git rev-parse --show-toplevel)" || exit 1

type mise || exit 1

mise install

mise x -- pre-commit install

mise cfg

mise tasks

find "$(git rev-parse --show-toplevel)"/.mise/tasks/ -type f -exec chmod +x {} \;
