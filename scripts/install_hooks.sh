#!/bin/bash
# Install local git hooks from .githooks directory

git config core.hooksPath .githooks
echo "✅ Git hooks installed from .githooks/"
chmod +x .githooks/*
