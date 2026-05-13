# Claude Quickstarts

Claude Quickstarts is a collection of projects designed to help developers quickly get started with building  applications using the Claude API. Each quickstart provides a foundation that you can easily build upon and customize for your specific needs.

## Getting Started

To use these quickstarts, you'll need an Claude API key. If you don't have one yet, you can sign up for free at [console.anthropic.com](https://console.anthropic.com).

## Available Quickstarts

### Customer Support Agent

A customer support agent powered by Claude. This project demonstrates how to leverage Claude's natural language understanding and generation capabilities to create an AI-assisted customer support system with access to a knowledge base.

[Go to Customer Support Agent Quickstart](./customer-support-agent)

### Financial Data Analyst

A financial data analyst powered by Claude. This project demonstrates how to leverage Claude's capabilities with interactive data visualization to analyze financial data via chat.

[Go to Financial Data Analyst Quickstart](./financial-data-analyst)

### Computer Use Demo

An environment and tools that Claude can use to control a desktop computer. This project demonstrates how to leverage the computer use capabilities of Claude, including support for the latest `computer_use_20251124` tool version with zoom actions.

[Go to Computer Use Demo Quickstart](./computer-use-demo)

### Computer Use Best Practices

A pedagogical, native-macOS reference implementation of a computer-use agent. Unlike the containerized Computer Use Demo, this project runs directly against the macOS desktop (run it in a VM!) and demonstrates common patterns for building more reliable and cost-effective computer-use agents: explicit tool definitions, correct image sizing and pruning, prompt caching, server-side compaction, batched tool calls, a sandboxed shell, and trajectory recording. It pairs with Anthropic's [computer-use best-practices guide](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude).

[Go to Computer Use Best Practices Quickstart](./computer-use-best-practices)

### Browser Use Demo

A complete reference implementation for browser automation powered by Claude. This project demonstrates how to give Claude the ability to navigate websites, inspect and interact with DOM elements, extract content, and fill forms using a custom Playwright-backed browser tool.

[Go to Browser Use Demo Quickstart](./browser-use-demo)

### Autonomous Coding Agent

An autonomous coding agent powered by the Claude Agent SDK. This project demonstrates a two-agent pattern (initializer + coding agent) that can build complete applications over multiple sessions, with progress persisted via git and a feature list that the agent works through incrementally.

[Go to Autonomous Coding Agent Quickstart](./autonomous-coding)

## General Usage

Each quickstart project comes with its own README and setup instructions. Generally, you'll follow these steps:

1. Clone this repository
2. Navigate to the specific quickstart directory
3. Install the required dependencies
4. Set up your Claude API key as an environment variable
5. Run the quickstart application

## Explore Further

To deepen your understanding of working with Claude and the Claude API, check out these resources:

- [Claude API Documentation](https://docs.claude.com)
- [Claude Cookbooks](https://github.com/anthropics/claude-cookbooks) - A collection of code snippets and guides for common tasks
- [Claude API Fundamentals Course](https://github.com/anthropics/courses/tree/master/anthropic_api_fundamentals)

## Contributing

We welcome contributions to the Claude Quickstarts repository! If you have ideas for new quickstart projects or improvements to existing ones, please open an issue or submit a pull request.

## Community and Support

- Join our [Anthropic Discord community](https://www.anthropic.com/discord) for discussions and support
- Check out the [Anthropic support documentation](https://support.anthropic.com) for additional help

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
