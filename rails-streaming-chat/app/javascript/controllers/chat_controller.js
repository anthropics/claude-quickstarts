import { Controller } from "@hotwired/stimulus"

export default class extends Controller {
  static targets = ["messages", "input", "submit"]

  connect() {
    this.scrollToBottom()
    this.observeNewMessages()
  }

  submitForm() {
    const input = this.inputTarget
    if (input.value.trim() === "") return

    this.submitTarget.disabled = true
    this.submitTarget.textContent = "..."
  }

  scrollToBottom() {
    const el = this.messagesTarget
    el.scrollTop = el.scrollHeight
  }

  observeNewMessages() {
    const observer = new MutationObserver(() => this.scrollToBottom())
    observer.observe(this.messagesTarget, {
      childList: true,
      subtree: true,
      characterData: true,
    })
  }
}
