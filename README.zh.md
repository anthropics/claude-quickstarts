# Claude Quickstarts

[English](README.md) | [简体中文](README.zh.md)

Claude Quickstarts 是一组精选的示例项目集合，旨在帮助开发者使用 Claude API 快速构建并部署应用程序。每个快速入门项目均提供了一个坚实的基础，您可以轻松在此基础上进行扩展，并根据具体需求进行定制。

## 快速入门

使用这些快速入门项目需要具备 Claude API 密钥。如果您尚未拥有密钥，可前往 [console.anthropic.com](https://console.anthropic.com) 免费注册获取。

## 可用快速入门项目

### 客户支持智能体 (Customer Support Agent)

由 Claude 驱动的客户支持智能体。该项目演示了如何利用 Claude 的自然语言理解与生成能力，构建一个能够访问专属知识库的 AI 辅助客户支持系统。

[前往客户支持智能体快速入门](./customer-support-agent)

### 金融数据分析师 (Financial Data Analyst)

由 Claude 驱动的金融数据分析师。该项目演示了如何结合 Claude 的推理能力与交互式数据可视化组件，通过对话方式对金融数据进行深入分析。

[前往金融数据分析师快速入门](./financial-data-analyst)

### 电脑操控演示 (Computer Use Demo)

供 Claude 控制桌面电脑的环境与工具集。该项目演示了如何利用 Claude 的计算机使用（Computer Use）能力，包含对最新 `computer_toolset_20260801` 工具集形态的支持，其中每个计算机操作均作为一个模型可通过名称直接调用的成员工具。

[前往电脑操控演示快速入门](./computer-use-demo)

### 电脑操控最佳实践 (Computer Use Best Practices)

一个教学性质的、基于 macOS 原生的计算机使用智能体参考实现。与容器化的电脑操控演示不同，该项目直接在 macOS 桌面环境中运行（请务必在虚拟机中运行！），并展示了构建更可靠、更具成本效益的计算机使用智能体的常用模式：显式工具定义、正确的图像尺寸调整与修剪、Prompt 缓存（Prompt Caching）、服务端上下文压缩（server-side compaction）、批量工具调用、沙箱化 Shell 以及轨迹记录。该项目配套 Anthropic 官方的[计算机与浏览器使用最佳实践指南](https://claude.com/blog/best-practices-for-computer-and-browser-use-with-claude)。

[前往电脑操控最佳实践快速入门](./computer-use-best-practices)

### 浏览器使用演示 (Browser Use Demo)

由 Claude 驱动的浏览器自动化完整参考实现。该项目演示了如何通过基于 Playwright 的自定义浏览器工具，赋予 Claude 浏览网站、检查并与 DOM 元素交互、提取网页内容以及填写表单的能力。

[前往浏览器使用演示快速入门](./browser-use-demo)

### 浏览器工具集快速入门 (Browser Toolset Quickstart)

基于 Python 和 TypeScript 实现的 Claude 浏览器工具集（`browser_toolset_20260801`）最小 CDP 示例。它包含一个通过 Chrome DevTools 协议（CDP）驱动单个 Chromium 标签页的轻量驱动程序、一个通过工具运行器执行该驱动的脚本，以及一个无需模型即可测试其功能的脚本。该项目旨在展示接口规范，非生产级代码。

[前往浏览器工具集快速入门](./browser-toolset)

### 计算机工具集快速入门 (Computer Toolset Quickstart)

基于 Python 和 TypeScript 实现的 Claude 计算机工具集（`computer_toolset_20260801`）最小 VNC 示例。它包含一个通过 VNC（直接基于 RFB 协议，无需第三方 VNC 库）驱动单个桌面环境的轻量驱动程序、一个通过工具运行器执行该驱动的脚本，以及一个无需模型即可测试其功能的脚本。该项目旨在展示接口规范，非生产级代码。

[前往计算机工具集快速入门](./computer-toolset)

### 自主编程智能体 (Autonomous Coding Agent)

由 Claude Agent SDK 驱动的自主编程智能体。该项目展示了双智能体协同模式（初始化智能体 + 编码智能体），能够跨越多个会话构建完整的应用程序，并通过 git 持久化项目进度，按照功能清单逐步递增实现各项特性。

[前往自主编程智能体快速入门](./autonomous-coding)

### 托管智能体：Chat SDK (Managed Agents: Chat SDK)

由 Claude Managed Agents（Claude 托管智能体）与 Vercel Chat SDK 驱动的浏览器聊天应用。该项目展示了如何将每次对话的持久化 Managed Agents 会话与聊天界面结合：研究分析师通过网页搜索开展研究，并逐字逐句流式传输研究简报，同时实时信息流中显示具体的工具调用过程。只需替换 Chat SDK 适配器，即可将相同的处理程序运行在 Slack、Teams、Discord、Telegram 或 WhatsApp 上。

[前往 Managed Agents Chat SDK 快速入门](./managed-agents/chat-sdk)

### 结合 CopilotKit 与 AG-UI 的托管智能体 (Managed Agents with CopilotKit and AG-UI)

基于 Claude Managed Agent 构建并使用 CopilotKit 渲染的个人财务助理聊天应用。该项目演示了如何将托管智能体会话桥接至 AG-UI 协议，通过事件增量（event deltas）实现逐字逐句的流式回复，并在聊天界面中将智能体工具调用渲染为交互式生成型 UI 组件。

[前往结合 CopilotKit 的 Managed Agents 快速入门](./managed-agents/copilot-kit-ag-ui)

### 托管智能体：每日工作简报 (Managed Agents: Daily Brief)

一个基于 Claude Managed Agents 构建的定时运行智能体，每个工作日自动读取您的 Slack 频道与 GitHub Pull Request，并向 Slack 发送一份精简的工作简报。该项目展示了完全通过 `ant apply` 应用的文件定义部署（包含 agent、环境、两个 memory store、vault 以及 cron 定时调度）、位于读写状态存储旁边的只读偏好存储，以及专为无人值守安全设计的运行步骤：按源独立书签、防重复提交账本，并将无法读取的数据源明确报告为不可读，而非错误视作平静的一天。

[前往 Managed Agents 每日简报快速入门](./managed-agents/daily-brief)

### 托管智能体：知识百科 (Managed Agents: Knowledge Wiki)

基于 Claude Managed Agents 构建的交易室（deal-room）知识百科系统。该项目演示了如何将整个文档语料库一次性提炼为具有版本控制的 memory-store 知识百科——通过并行抽取会话、冲突消解轮次以及定向整合沉淀——随后利用该百科回答分析师的重复提问，每条事实均附带精确溯源证据，而每轮问答的 Token 成本仅为原始文档检索的一小部分。配套示例取自美国 SEC EDGAR 公开申报文件的真实并购数据室。

[前往 Managed Agents 知识百科快速入门](./managed-agents/knowledge-wiki)

### 托管智能体：Linear (Managed Agents: Linear)

在 Linear 中可通过 `@mention` 提及或分配任务的智能体，由 Claude Managed Agent 提供支持。该项目展示了 Linear Agent 平台上的无状态 Webhook 桥接机制：`AgentSessionEvent` 会创建一个 Managed Agents 会话，并将 Linear 会话 ID 与组织 ID 存储在会话元数据中，随后 `session.status_idled` Webhook 读取该元数据并将回复发表为评论。通过 `actor=app` 模式的 Linear OAuth 完成安装。

[前往 Managed Agents Linear 快速入门](./managed-agents/linear)

### 托管智能体：MCP 服务端 (TypeScript) (Managed Agents: MCP Server (TypeScript))

将 Claude Managed Agents Sessions API 封装暴露为 9 项工具的 MCP（Model Context Protocol）服务器。该项目展示了如何让 Claude Desktop、Claude Code 或 claude.ai 驱动工作区中已有的智能体：列出智能体、创建会话、发送消息并通过 stdio 或 Streamable HTTP 等待回复。其中 `wait_for_idle` 工具将整个会话事件流转化为单次请求/响应调用，并通过智能体白名单严格限制 Bearer Token 持有者的访问范围。

[前往 Managed Agents MCP Server (TypeScript) 快速入门](./managed-agents/mcp-server-typescript)

### 托管智能体：自驾公路旅行规划师 (Managed Agents: Road Trip Planner)

直接基于 Claude Managed Agents 会话构建的国家公园公路旅行规划应用，采用 Next.js 开发，无需任何第三方聊天框架和数据库。该项目在单一屏幕上展示了四项前沿 API 特性：基于会话事件流中的 `event_deltas` 进行逐 Token 流式传输、在特定请求位置（`injection_location`）注入 Vault 机密凭据、使用 `agent_with_overrides` 进行单会话模型重写覆盖，以及由 `multiagent` 协调器将规划草案转交给同一会话线程内的审阅者智能体。

[前往 Managed Agents 公路旅行规划师快速入门](./managed-agents/roadtrip-planner)

### 托管智能体：Sentry (Managed Agents: Sentry)

基于 Claude Managed Agents 构建的定时 Sentry 异常分流智能体。该项目演示了无需常驻宿主进程、完全基于 Cron 调度的定时会话启动方案、用于引导式配置的 Sentry Agent Plugin，以及持久化存储在 Vault 中可自动刷新的 MCP OAuth 凭据，用于错误分流与 Seer 根本原因分析。

[前往 Managed Agents Sentry 快速入门](./managed-agents/sentry)

### 托管智能体：Slack (Managed Agents: Slack)

由 Claude Managed Agent 驱动的 Slack 机器人。该项目展示了一种无状态的 Webhook 桥接方式：通过 `@mention` 提及触发创建 Managed Agents 会话，并将频道和线程信息保存在会话元数据中，`session.status_idled` Webhook 读取该元数据并在对应的线程中直接回复。无需数据库与长连接。

[前往 Managed Agents Slack 快速入门](./managed-agents/slack)

## 通用使用指南

每个快速入门项目均配有专属的 README 与配置说明。通常情况下，您只需遵循以下步骤：

1. 克隆本仓库：
   ```shell
   git clone https://github.com/anthropics/claude-quickstarts.git
   ```
2. 进入特定的快速入门项目目录
3. 安装所需的依赖项
4. 配置您的 Claude API 密钥作为环境变量
5. 运行快速入门应用程序

## 深入探索

若要深入了解如何使用 Claude 和 Claude API，请参阅以下资源：

- [Claude API 官方文档](https://docs.claude.com)
- [Claude Cookbooks](https://github.com/anthropics/claude-cookbooks) - 常见任务的代码示例与指南集合
- [Claude API 基础教程课程](https://github.com/anthropics/courses/tree/master/anthropic_api_fundamentals)

## 参与贡献

我们非常欢迎对 Claude Quickstarts 仓库的贡献！如果您有关于新快速入门项目的想法，或对现有项目的改进建议，请提交 Issue 或发起 Pull Request。

## 社区与支持

- 加入我们的 [Anthropic Discord 社区](https://www.anthropic.com/discord) 参与技术讨论并获取支持
- 查阅 [Anthropic 官方技术支持文档](https://support.anthropic.com) 获取更多帮助

## 开源许可证

本项目采用 MIT 许可证开源 - 详见 [LICENSE](LICENSE) 文件。

---

> **免责声明**：本文档由社区志愿者进行本地化翻译，旨在促进跨语言的技术交流与学习。如翻译内容与[英文原版](README.md)存在出入，请以英文原版为准。
