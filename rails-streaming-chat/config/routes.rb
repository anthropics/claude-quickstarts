Rails.application.routes.draw do
  root "chats#index"
  resources :chats, only: [:create]
  delete "/chats", to: "chats#destroy", as: :clear_chat
end
