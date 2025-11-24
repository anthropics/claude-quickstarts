<project_specification>
  <project_name>Claude.ai Clone - AI Chat Interface</project_name>

  <overview>
    Build a fully functional clone of claude.ai, Anthropic's conversational AI interface. The application should
    provide a clean, modern chat interface for interacting with Claude via the API, including features like
    conversation management, artifact rendering, project organization, multiple model selection, and advanced
    settings. The UI should closely match claude.ai's design using Tailwind CSS with a focus on excellent
    user experience and responsive design.
  </overview>

  <technology_stack>
    <api_key>
        You can use an API key located at /tmp/api-key for testing. You will not be allowed to read this file, but you can reference it in code.
    </api_key>
    <frontend>
      <framework>React with Vite</framework>
      <styling>Tailwind CSS (via CDN)</styling>
      <state_management>React hooks and context</state_management>
      <routing>React Router for navigation</routing>
      <markdown>React Markdown for message rendering</markdown>
      <code_highlighting>Syntax highlighting for code blocks</code_highlighting>
      <port>Only launch on port {frontend_port}</port>
    </frontend>
    <backend>
      <runtime>Node.js with Express</runtime>
      <database>SQLite with better-sqlite3</database>
      <api_integration>Claude API for chat completions</api_integration>
      <streaming>Server-Sent Events for streaming responses</streaming>
    </backend>
    <communication>
      <api>RESTful endpoints</api>
      <streaming>SSE for real-time message streaming</streaming>
      <claude_api>Integration with Claude API using Anthropic SDK</claude_api>
    </communication>
  </technology_stack>

  <prerequisites>
    <environment_setup>
      - Repository includes .env with VITE_ANTHROPIC_API_KEY configured
      - Frontend dependencies pre-installed via pnpm
      - Backend code goes in /server directory
      - Install backend dependencies as needed
    </environment_setup>
  </prerequisites>

  <core_features>
    <chat_interface>
      - Clean, centered chat layout with message bubbles
      - Streaming message responses with typing indicator
      - Markdown rendering with proper formatting
      - Code blocks with syntax highlighting and copy button
      - LaTeX/math equation rendering
      - Image upload and display in messages
      - Multi-turn conversations with context
      - Message editing and regeneration
      - Stop generation button during streaming
      - Input field with auto-resize textarea
      - Character count and token estimation
      - Keyboard shortcuts (Enter to send, Shift+Enter for newline)
    </chat_interface>

    <artifacts>
      - Artifact detection and rendering in side panel
      - Code artifact viewer with syntax highlighting
      - HTML/SVG preview with live rendering
      - React component preview
      - Mermaid diagram rendering
      - Text document artifacts
      - Artifact editing and re-prompting
      - Full-screen artifact view
      - Download artifact content
      - Artifact versioning and history
    </artifacts>

    <conversation_management>
      - Create new conversations
      - Conversation list in sidebar
      - Rename conversations
      - Delete conversations
      - Search conversations by title/content
      - Pin important conversations
      - Archive conversations
      - Conversation folders/organization
      - Duplicate conversation
      - Export conversation (JSON, Markdown, PDF)
      - Conversation timestamps (created, last updated)
      - Unread message indicators
    </conversation_management>

    <projects>
      - Create projects to group related conversations
      - Project knowledge base (upload documents)
      - Project-specific custom instructions
      - Share projects with team (mock feature)
      - Project settings and configuration
      - Move conversations between projects
      - Project templates
      - Project analytics (usage stats)
    </projects>

    <model_selection>
      - Model selector dropdown with the following models:
        - Claude Sonnet 4.5 (claude-sonnet-4-5-20250929) - default
        - Claude Haiku 4.5 (claude-haiku-4-5-20251001)
        - Claude Opus 4.1 (claude-opus-4-1-20250805)
      - Model capabilities display
      - Context window indicator
      - Model-specific pricing info (display only)
      - Switch models mid-conversation
      - Model comparison view
    </model_selection>

    <custom_instructions>
      - Global custom instructions
      - Project-specific custom instructions
      - Conversation-specific system prompts
      - Custom instruction templates
      - Preview how instructions affect responses
    </custom_instructions>

    <settings_preferences>
      - Theme selection (Light, Dark, Auto)
      - Font size adjustment
      - Message density (compact, comfortable, spacious)
      - Code theme selection
      - Language preferences
      - Accessibility options
      - Keyboard shortcuts reference
      - Data export options
      - Privacy settings
      - API key management
    </settings_preferences>

    <advanced_features>
      - Temperature control slider
      - Max tokens adjustment
      - Top-p (nucleus sampling) control
      - System prompt override
      - Thinking/reasoning mode toggle
      - Multi-modal input (text + images)
      - Voice input (optional, mock UI)
      - Response suggestions
      - Related prompts
      - Conversation branching
    </advanced_features>

    <collaboration>
      - Share conversation via link (read-only)
      - Export conversation formats
      - Conversation templates
      - Prompt library
      - Share artifacts
      - Team workspaces (mock UI)
    </collaboration>

    <search_discovery>
      - Search across all conversations
      - Filter by project, date, model
      - Prompt library with categories
      - Example conversations
      - Quick actions menu
      - Command palette (Cmd/Ctrl+K)
    </search_discovery>

    <usage_tracking>
      - Token usage display per message
      - Conversation cost estimation
      - Daily/monthly usage dashboard
      - Usage limits and warnings
      - API quota tracking
    </usage_tracking>

    <onboarding>
      - Welcome screen for new users
      - Feature tour highlights
      - Example prompts to get started
      - Quick tips and best practices
      - Keyboard shortcuts tutorial
    </onboarding>

    <accessibility>
      - Full keyboard navigation
      - Screen reader support
      - ARIA labels and roles
      - High contrast mode
      - Focus management
      - Reduced motion support
    </accessibility>

    <responsive_design>
      - Mobile-first responsive layout
      - Touch-optimized interface
      - Collapsible sidebar on mobile
      - Swipe gestures for navigation
      - Adaptive artifact display
      - Progressive Web App (PWA) support
    </responsive_design>
  </core_features>

  <database_schema>
    <tables>
      <users>
        - id, email, name, avatar_url
        - created_at, last_login
        - preferences (JSON: theme, font_size, etc.)
        - custom_instructions
      </users>

      <projects>
        - id, user_id, name, description, color
        - custom_instructions, knowledge_base_path
        - created_at, updated_at
        - is_archived, is_pinned
      </projects>

      <conversations>
        - id, user_id, project_id, title
        - model, created_at, updated_at, last_message_at
        - is_archived, is_pinned, is_deleted
        - settings (JSON: temperature, max_tokens, etc.)
        - token_count, message_count
      </conversations>

      <messages>
        - id, conversation_id, role (user/assistant/system)
        - content, created_at, edited_at
        - tokens, finish_reason
        - images (JSON array of image data)
        - parent_message_id (for branching)
      </messages>

      <artifacts>
        - id, message_id, conversation_id
        - type (code/html/svg/react/mermaid/text)
        - title, identifier, language
        - content, version
        - created_at, updated_at
      </artifacts>

      <shared_conversations>
        - id, conversation_id, share_token
        - created_at, expires_at, view_count
        - is_public
      </shared_conversations>

      <prompt_library>
        - id, user_id, title, description
        - prompt_template, category, tags (JSON)
        - is_public, usage_count
        - created_at, updated_at
      </prompt_library>

      <conversation_folders>
        - id, user_id, project_id, name, parent_folder_id
        - created_at, position
      </conversation_folders>

      <conversation_folder_items>
        - id, folder_id, conversation_id
      </conversation_folder_items>

      <usage_tracking>
        - id, user_id, conversation_id, message_id
        - model, input_tokens, output_tokens
        - cost_estimate, created_at
      </usage_tracking>

      <api_keys>
        - id, user_id, key_name, api_key_hash
        - created_at, last_used_at
        - is_active
      </api_keys>
    </tables>
  </database_schema>

  <api_endpoints_summary>
    <authentication>
      - POST /api/auth/login
      - POST /api/auth/logout
      - GET /api/auth/me
      - PUT /api/auth/profile
    </authentication>

    <conversations>
      - GET /api/conversations
      - POST /api/conversations
      - GET /api/conversations/:id
      - PUT /api/conversations/:id
      - DELETE /api/conversations/:id
      - POST /api/conversations/:id/duplicate
      - POST /api/conversations/:id/export
      - PUT /api/conversations/:id/archive
      - PUT /api/conversations/:id/pin
      - POST /api/conversations/:id/branch
    </conversations>

    <messages>
      - GET /api/conversations/:id/messages
      - POST /api/conversations/:id/messages
      - PUT /api/messages/:id
      - DELETE /api/messages/:id
      - POST /api/messages/:id/regenerate
      - GET /api/messages/stream (SSE endpoint)
    </messages>

    <artifacts>
      - GET /api/conversations/:id/artifacts
      - GET /api/artifacts/:id
      - PUT /api/artifacts/:id
      - DELETE /api/artifacts/:id
      - POST /api/artifacts/:id/fork
      - GET /api/artifacts/:id/versions
    </artifacts>

    <projects>
      - GET /api/projects
      - POST /api/projects
      - GET /api/projects/:id
      - PUT /api/projects/:id
      - DELETE /api/projects/:id
      - POST /api/projects/:id/knowledge
      - GET /api/projects/:id/conversations
      - PUT /api/projects/:id/settings
    </projects>

    <sharing>
      - POST /api/conversations/:id/share
      - GET /api/share/:token
      - DELETE /api/share/:token
      - PUT /api/share/:token/settings
    </sharing>

    <prompts>
      - GET /api/prompts/library
      - POST /api/prompts/library
      - GET /api/prompts/:id
      - PUT /api/prompts/:id
      - DELETE /api/prompts/:id
      - GET /api/prompts/categories
      - GET /api/prompts/examples
    </prompts>

    <search>
      - GET /api/search/conversations?q=query
      - GET /api/search/messages?q=query
      - GET /api/search/artifacts?q=query
      - GET /api/search/prompts?q=query
    </search>

    <folders>
      - GET /api/folders
      - POST /api/folders
      - PUT /api/folders/:id
      - DELETE /api/folders/:id
      - POST /api/folders/:id/items
      - DELETE /api/folders/:id/items/:conversationId
    </folders>

    <usage>
      - GET /api/usage/daily
      - GET /api/usage/monthly
      - GET /api/usage/by-model
      - GET /api/usage/conversations/:id
    </usage>

    <settings>
      - GET /api/settings
      - PUT /api/settings
      - GET /api/settings/custom-instructions
      - PUT /api/settings/custom-instructions
    </settings>

    <claude_api>
      - POST /api/claude/chat (proxy to Claude API)
      - POST /api/claude/chat/stream (streaming proxy)
      - GET /api/claude/models
      - POST /api/claude/images/upload
    </claude_api>
  </api_endpoints_summary>

  <ui_layout>
    <main_structure>
      - Three-column layout: sidebar (conversations), main (chat), panel (artifacts)
      - Collapsible sidebar with resize handle
      - Responsive breakpoints: mobile (single column), tablet (two column), desktop (three column)
      - Persistent header with project/model selector
      - Bottom input area with send button and options
    </main_structure>

    <sidebar_left>
      - New chat button (prominent)
      - Project selector dropdown
      - Search conversations input
      - Conversations list (grouped by date: Today, Yesterday, Previous 7 days, etc.)
      - Folder tree view (collapsible)
      - Settings gear icon at bottom
      - User profile at bottom
    </sidebar_left>

    <main_chat_area>
      - Conversation title (editable inline)
      - Model selector badge
      - Message history (scrollable)
      - Welcome screen for new conversations
      - Suggested prompts (empty state)
      - Input area with formatting toolbar
      - Attachment button for images
      - Send button with loading state
      - Stop generation button
    </main_chat_area>

    <artifacts_panel>
      - Artifact header with title and type badge
      - Code editor or preview pane
      - Tabs for multiple artifacts
      - Full-screen toggle
      - Download button
      - Edit/Re-prompt button
      - Version selector
      - Close panel button
    </artifacts_panel>

    <modals_overlays>
      - Settings modal (tabbed interface)
      - Share conversation modal
      - Export options modal
      - Project settings modal
      - Prompt library modal
      - Command palette overlay
      - Keyboard shortcuts reference
    </modals_overlays>
  </ui_layout>

  <design_system>
    <color_palette>
      - Primary: Orange/amber accent (#CC785C claude-style)
      - Background: White (light mode), Dark gray (#1A1A1A dark mode)
      - Surface: Light gray (#F5F5F5 light), Darker gray (#2A2A2A dark)
      - Text: Near black (#1A1A1A light), Off-white (#E5E5E5 dark)
      - Borders: Light gray (#E5E5E5 light), Dark gray (#404040 dark)
      - Code blocks: Monaco editor theme
    </color_palette>

    <typography>
      - Sans-serif system font stack (Inter, SF Pro, Roboto, system-ui)
      - Headings: font-semibold
      - Body: font-normal, leading-relaxed
      - Code: Monospace (JetBrains Mono, Consolas, Monaco)
      - Message text: text-base (16px), comfortable line-height
    </typography>

    <components>
      <message_bubble>
        - User messages: Right-aligned, subtle background
        - Assistant messages: Left-aligned, no background
        - Markdown formatting with proper spacing
        - Inline code with bg-gray-100 background
        - Code blocks with syntax highlighting
        - Copy button on code blocks
      </message_bubble>

      <buttons>
        - Primary: Orange/amber background, white text, rounded
        - Secondary: Border style with hover fill
        - Icon buttons: Square with hover background
        - Disabled state: Reduced opacity, no pointer events
      </buttons>

      <inputs>
        - Rounded borders with focus ring
        - Textarea auto-resize
        - Placeholder text in gray
        - Error states in red
        - Character counter
      </inputs>

      <cards>
        - Subtle border or shadow
        - Rounded corners (8px)
        - Padding: p-4 to p-6
        - Hover state: slight shadow increase
      </cards>
    </components>

    <animations>
      - Smooth transitions (150-300ms)
      - Fade in for new messages
      - Slide in for sidebar
      - Typing indicator animation
      - Loading spinner for generation
      - Skeleton loaders for content
    </animations>
  </design_system>

  <key_interactions>
    <message_flow>
      1. User types message in input field
      2. Optional: Attach images via button
      3. Click send or press Enter
      4. Message appears in chat immediately
      5. Typing indicator shows while waiting
      6. Response streams in word by word
      7. Code blocks render with syntax highlighting
      8. Artifacts detected and rendered in side panel
      9. Message complete, enable regenerate option
    </message_flow>

    <artifact_flow>
      1. Assistant generates artifact in response
      2. Artifact panel slides in from right
      3. Content renders (code with highlighting or live preview)
      4. User can edit artifact inline
      5. "Re-prompt" button to iterate with Claude
      6. Download or copy artifact content
      7. Full-screen mode for detailed work
      8. Close panel to return to chat focus
    </artifact_flow>

    <conversation_management>
      1. Click "New Chat" to start fresh conversation
      2. Conversations auto-save with first message
      3. Auto-generate title from first exchange
      4. Click title to rename inline
      5. Drag conversations into folders
      6. Right-click for context menu (pin, archive, delete, export)
      7. Search filters conversations in real-time
      8. Click conversation to switch context
    </conversation_management>
  </key_interactions>

  <implementation_steps>
    <step number="1">
      <title>Setup Project Foundation and Database</title>
      <tasks>
        - Initialize Express server with SQLite database
        - Set up Claude API client with streaming support
        - Create database schema with migrations
        - Implement authentication endpoints
        - Set up basic CORS and middleware
        - Create health check endpoint
      </tasks>
    </step>

    <step number="2">
      <title>Build Core Chat Interface</title>
      <tasks>
        - Create main layout with sidebar and chat area
        - Implement message display with markdown rendering
        - Add streaming message support with SSE
        - Build input area with auto-resize textarea
        - Add code block syntax highlighting
        - Implement stop generation functionality
        - Add typing indicators and loading states
      </tasks>
    </step>

    <step number="3">
      <title>Conversation Management</title>
      <tasks>
        - Create conversation list in sidebar
        - Implement new conversation creation
        - Add conversation switching
        - Build conversation rename functionality
        - Implement delete with confirmation
        - Add conversation search
        - Create conversation grouping by date
      </tasks>
    </step>

    <step number="4">
      <title>Artifacts System</title>
      <tasks>
        - Build artifact detection from Claude responses
        - Create artifact rendering panel
        - Implement code artifact viewer
        - Add HTML/SVG live preview
        - Build artifact editing interface
        - Add artifact versioning
        - Implement full-screen artifact view
      </tasks>
    </step>

    <step number="5">
      <title>Projects and Organization</title>
      <tasks>
        - Create projects CRUD endpoints
        - Build project selector UI
        - Implement project-specific custom instructions
        - Add folder system for conversations
        - Create drag-and-drop organization
        - Build project settings panel
      </tasks>
    </step>

    <step number="6">
      <title>Advanced Features</title>
      <tasks>
        - Add model selection dropdown
        - Implement temperature and parameter controls
        - Build image upload functionality
        - Create message editing and regeneration
        - Add conversation branching
        - Implement export functionality
      </tasks>
    </step>

    <step number="7">
      <title>Settings and Customization</title>
      <tasks>
        - Build settings modal with tabs
        - Implement theme switching (light/dark)
        - Add custom instructions management
        - Create keyboard shortcuts
        - Build prompt library
        - Add usage tracking dashboard
      </tasks>
    </step>

    <step number="8">
      <title>Sharing and Collaboration</title>
      <tasks>
        - Implement conversation sharing with tokens
        - Create public share view
        - Add export to multiple formats
        - Build prompt templates
        - Create example conversations
      </tasks>
    </step>

    <step number="9">
      <title>Polish and Optimization</title>
      <tasks>
        - Optimize for mobile responsiveness
        - Add command palette (Cmd+K)
        - Implement comprehensive keyboard navigation
        - Add onboarding flow
        - Create accessibility improvements
        - Performance optimization and caching
      </tasks>
    </step>
  </implementation_steps>

  <success_criteria>
    <functionality>
      - Streaming chat responses work smoothly
      - Artifact detection and rendering accurate
      - Conversation management intuitive and reliable
      - Project organization clear and useful
      - Image upload and display working
      - All CRUD operations functional
    </functionality>

    <user_experience>
      - Interface matches claude.ai design language
      - Responsive on all device sizes
      - Smooth animations and transitions
      - Fast response times and minimal lag
      - Intuitive navigation and workflows
      - Clear feedback for all actions
    </user_experience>

    <technical_quality>
      - Clean, maintainable code structure
      - Proper error handling throughout
      - Secure API key management
      - Optimized database queries
      - Efficient streaming implementation
      - Comprehensive testing coverage
    </technical_quality>

    <design_polish>
      - Consistent with claude.ai visual design
      - Beautiful typography and spacing
      - Smooth animations and micro-interactions
      - Excellent contrast and accessibility
      - Professional, polished appearance
      - Dark mode fully implemented
    </design_polish>
  </success_criteria>
</project_specification>
