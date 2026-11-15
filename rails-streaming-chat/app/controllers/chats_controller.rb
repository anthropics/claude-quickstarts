class ChatsController < ApplicationController
  include ActionController::Live

  def index
    @messages = session[:messages] || []
  end

  def create
    user_content = params[:message].to_s.strip
    return redirect_to(root_path) if user_content.empty?

    session[:messages] ||= []
    session[:messages] << { "role" => "user", "content" => user_content }

    response.headers["Content-Type"] = "text/vnd.turbo-stream.html; charset=utf-8"

    # Append the user message to the chat
    response.stream.write(
      turbo_stream.append("messages", partial: "chats/message",
        locals: { role: "user", content: user_content })
    )

    # Append an empty assistant message container
    response.stream.write(
      turbo_stream.append("messages", partial: "chats/message",
        locals: { role: "assistant", content: "", id: "assistant-response" })
    )

    # Stream Claude's response, replacing the assistant container with accumulated text
    accumulated = ""
    stream = ANTHROPIC_CLIENT.messages.stream(
      model: CLAUDE_MODEL,
      max_tokens: 2048,
      system: "You are a helpful assistant. Be concise and clear.",
      messages: session[:messages].map { |m| { role: m["role"].to_sym, content: m["content"] } }
    )

    stream.text.each do |chunk|
      accumulated += chunk
      response.stream.write(
        turbo_stream.replace("assistant-response", partial: "chats/message",
          locals: { role: "assistant", content: accumulated, id: "assistant-response" })
      )
    end

    # Save the complete response to session for multi-turn
    session[:messages] << { "role" => "assistant", "content" => accumulated }

    # Clear the input field
    response.stream.write(
      turbo_stream.replace("message-form", partial: "chats/form")
    )

    # Scroll to bottom
    response.stream.write(
      turbo_stream.append("messages",
        "<template data-chat-target='scrollTrigger'></template>")
    )
  rescue => e
    Rails.logger.error("Streaming error: #{e.message}")
    response.stream.write(
      turbo_stream.replace("assistant-response", partial: "chats/message",
        locals: { role: "assistant", content: "Sorry, something went wrong. Please try again.", id: "assistant-response" })
    )
  ensure
    response.stream.close
  end

  def destroy
    session.delete(:messages)
    redirect_to root_path
  end
end
