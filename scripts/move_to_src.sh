#!/bin/bash
# Migration script to reorganize repository structure

set -e

echo "=== TradingAgents Repository Reorganization ==="
echo ""

# Create new directory structure
echo "Creating new directory structure..."
mkdir -p src/tradingagents/{agents,dataflows,graph,llm_clients}
mkdir -p scripts
mkdir -p config
mkdir -p docs
mkdir -p launchagent
mkdir -p data/{logs,results,memory}

echo "Done!"
echo ""
echo "New structure:"
tree -L 3 -d 2>/dev/null || find . -maxdepth 3 -type d | grep -v ".git" | sort

echo ""
echo "=== Next Steps ==="
echo "1. Move tradingagents/ package to src/tradingagents/"
echo "2. Move main scripts to scripts/"
echo "3. Move docs to docs/"
echo "4. Update imports"
echo "5. Update pyproject.toml"
