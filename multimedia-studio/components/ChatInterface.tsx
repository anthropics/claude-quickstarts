'use client';

import { useState } from 'react';
import { useStudio } from '@/lib/store';
import { createClient } from '@/lib/promptchan-client';
import { Loader, Send } from 'lucide-react';

export default function ChatInterface() {
  const { apiKey, chatHistory, addChatMessage } = useStudio();
  const [message, setMessage] = useState('');
  const [charName, setCharName] = useState('');
  const [charPersonality, setCharPersonality] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showSetup, setShowSetup] = useState(!charName);

  const handleSend = async () => {
    if (!message.trim()) return;

    setLoading(true);
    setError('');

    try {
      const client = createClient(apiKey);
      const result = await client.chat({
        message,
        characterData: charName
          ? {
              name: charName,
              personality: charPersonality,
            }
          : undefined,
        chatHistory,
      });

      addChatMessage({
        id: Math.random().toString(36).substr(2, 9),
        role: 'user',
        content: message,
        timestamp: Date.now(),
      });

      addChatMessage({
        id: Math.random().toString(36).substr(2, 9),
        role: 'assistant',
        content: result.message,
        timestamp: Date.now(),
      });

      setMessage('');
    } catch (err: any) {
      setError(err.message || 'Failed to send message');
    } finally {
      setLoading(false);
    }
  };

  if (showSetup) {
    return (
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 max-w-2xl mx-auto">
        <h2 className="text-lg font-bold text-white mb-4">💬 Chat Setup</h2>

        <div className="space-y-4 mb-6">
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Character Name (optional)</label>
            <input
              type="text"
              value={charName}
              onChange={(e) => setCharName(e.target.value)}
              placeholder="e.g., Luna, Alex, etc."
              className="w-full px-4 py-2 bg-slate-900 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-400"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">Personality (optional)</label>
            <textarea
              value={charPersonality}
              onChange={(e) => setCharPersonality(e.target.value)}
              placeholder="Describe the character's personality and traits..."
              className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-400 resize-none h-20"
            />
          </div>
        </div>

        <button
          onClick={() => setShowSetup(false)}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded transition-colors"
        >
          Start Chatting
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto bg-slate-800 border border-slate-700 rounded-lg overflow-hidden flex flex-col h-[600px]">
      {/* Header */}
      <div className="bg-slate-700 p-4 border-b border-slate-600 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white">Chat</h2>
          {charName && <p className="text-sm text-slate-400">Chatting with {charName}</p>}
        </div>
        <button
          onClick={() => setShowSetup(true)}
          className="text-xs bg-slate-600 hover:bg-slate-500 text-white px-3 py-1 rounded transition-colors"
        >
          Change
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {chatHistory.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-400">
            <p>Start a conversation...</p>
          </div>
        ) : (
          chatHistory.map((msg) => (
            <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-xs px-4 py-2 rounded-lg ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-700 text-slate-100'
                }`}
              >
                <p className="text-sm">{msg.content}</p>
              </div>
            </div>
          ))
        )}
        {error && (
          <div className="p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-slate-600 p-4 bg-slate-700/50">
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Type your message..."
            disabled={loading}
            className="flex-1 px-4 py-2 bg-slate-900 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-400 disabled:opacity-50"
          />
          <button
            onClick={handleSend}
            disabled={loading || !message.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white px-4 py-2 rounded transition-colors flex items-center justify-center gap-2"
          >
            {loading ? (
              <Loader className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
