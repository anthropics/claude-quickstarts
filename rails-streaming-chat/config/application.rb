require_relative "boot"

require "rails"
require "action_controller/railtie"
require "action_view/railtie"

module RailsStreamingChat
  class Application < Rails::Application
    config.load_defaults 8.0

    # Session-based app, no database needed
    config.session_store :cookie_store, key: "_claude_chat_session"
    config.secret_key_base = ENV.fetch("SECRET_KEY_BASE") { SecureRandom.hex(64) }
  end
end
