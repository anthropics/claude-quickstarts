# Rails Streaming Chat

A minimal Rails 8 chat application that streams responses from Claude using Turbo Streams over HTTP. No database, no Redis, no Action Cable — just Rails, Hotwire, and the Anthropic API.

## Features

- Real-time streaming responses from Claude via `ActionController::Live`
- Multi-turn conversation maintained in session
- Turbo Stream updates for a seamless chat experience
- Responsive UI with Tailwind CSS
- Zero external dependencies beyond the Anthropic API

## Prerequisites

- Ruby 3.2+
- An [Anthropic API key](https://console.anthropic.com)

## Getting Started

1. Clone this repository and navigate to the quickstart:

   ```bash
   git clone https://github.com/anthropics/claude-quickstarts.git
   cd claude-quickstarts/rails-streaming-chat
   ```

2. Install dependencies:

   ```bash
   bundle install
   ```

3. Set your API key:

   ```bash
   export ANTHROPIC_API_KEY="your-api-key-here"
   ```

4. Start the server:

   ```bash
   bin/rails server
   ```

5. Open [http://localhost:3000](http://localhost:3000) and start chatting!

## How It Works

1. **User submits a message** via a standard form POST
2. **`ChatsController#create`** receives the message and opens an HTTP streaming response
3. **Turbo Stream fragments** are written to the response as Claude generates text chunks
4. **The browser** processes each Turbo Stream fragment in real-time, updating the chat UI
5. **Session storage** maintains the conversation history for multi-turn context

The key pattern is `ActionController::Live` combined with the Anthropic SDK's streaming API:

```ruby
stream = ANTHROPIC_CLIENT.messages.stream(
  model: "claude-sonnet-4-5-20250929",
  max_tokens: 1024,
  messages: session[:messages]
)

stream.text.each do |chunk|
  response.stream.write(turbo_stream_replace("response", accumulated))
end
```

## Technology Stack

| Technology | Purpose |
|-----------|---------|
| [Rails 8](https://rubyonrails.org/) | Web framework |
| [Anthropic Ruby SDK](https://github.com/anthropics/anthropic-sdk-ruby) | Claude API client |
| [Hotwire (Turbo + Stimulus)](https://hotwired.dev/) | Real-time UI updates |
| [Tailwind CSS](https://tailwindcss.com/) | Styling |
| [Puma](https://puma.io/) | Web server |

## Customization

- **Change the model**: Edit `CLAUDE_MODEL` in `config/initializers/anthropic.rb`
- **Add a system prompt**: Modify the `system:` parameter in `ChatsController#create`
- **Persist conversations**: Replace session storage with ActiveRecord

## Disclaimer

This quickstart is intended as a starting point for building with Claude. For production use, consider adding authentication, rate limiting, error handling, and database-backed conversation storage.
