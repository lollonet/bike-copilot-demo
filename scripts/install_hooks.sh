#!/bin/bash
# Install local git hooks from .githooks directory

chmod +x .githooks/*
git config core.hooksPath .githooks
echo "✅ Git hooks installed from .githooks/"