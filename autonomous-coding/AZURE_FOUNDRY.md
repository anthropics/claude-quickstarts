# Azure Foundry Setup Guide

This guide explains how to run the autonomous coding demo with Azure AI Foundry (Microsoft Foundry).

## Prerequisites

1. Azure AI Foundry account with Claude model deployed
2. Your deployment name (e.g., "claude-sonnet-4-5" or whatever you named it)
3. Foundry API credentials configured

## Quick Setup (Recommended)

### 1. Create a .env file (one-time setup)

```bash
cd autonomous-coding

# Copy the example file
cp .env.example .env

# Edit the file with your credentials
nano .env  # or use your preferred editor
```

Edit `.env` with your values:
```bash
ANTHROPIC_FOUNDRY_API_KEY=your-actual-api-key
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_RESOURCE=sds-contentunderstandin-resource
CLAUDE_MODEL=claude-sonnet-4-5
```

### 2. Run the Demo

Now you can run experiments without setting environment variables each time:

```bash
python3 autonomous_agent_demo.py --project-dir legal-workbench-v2 --max-iterations 3
```

That's it! The script automatically loads your `.env` file.

## Alternative: Environment Variables

If you prefer not to use a `.env` file, you can export variables in your shell:

```bash
export ANTHROPIC_FOUNDRY_API_KEY='your-api-key'
export CLAUDE_CODE_USE_FOUNDRY=1
export ANTHROPIC_FOUNDRY_RESOURCE='your-resource-name'
export CLAUDE_MODEL='claude-sonnet-4-5'  # Optional, defaults to 'claude-sonnet-4-5'
```

## Default Behavior

- **Default model for Foundry**: `claude-sonnet-4-5`
- If your deployment has a different name, set `CLAUDE_MODEL` in `.env` or use `--model` flag
- Priority: `--model` flag > `CLAUDE_MODEL` env var > default (`claude-sonnet-4-5`)

```bash
cd autonomous-coding
python3 autonomous_agent_demo.py --project-dir legal-workbench-v2 --max-iterations 3
```

Or specify the model via CLI:

```bash
python3 autonomous_agent_demo.py \
  --model your-deployment-name \
  --project-dir legal-workbench-v2 \
  --max-iterations 3
```

## Verification

After starting, you should see:

```
Using model/deployment: your-deployment-name
(Azure Foundry mode)

Created security settings at ...
```

If you see a `DeploymentNotFound` error, check that:
1. `CLAUDE_MODEL` matches your actual deployment name in Foundry
2. `ANTHROPIC_FOUNDRY_RESOURCE` is correct
3. Your API key has access to the deployment

## Common Issues

### "Error: Model/deployment name required for Azure Foundry"
You need to set `CLAUDE_MODEL` environment variable or use `--model` flag.

### "DeploymentNotFound" error
Your `CLAUDE_MODEL` doesn't match any deployment in your Foundry resource. Check your deployment name in the Azure portal.

### Authentication errors
Verify all Foundry environment variables are set correctly, especially:
- `ANTHROPIC_FOUNDRY_API_KEY`
- `CLAUDE_CODE_USE_FOUNDRY=1`
- `ANTHROPIC_FOUNDRY_RESOURCE`
