'use client';

import { useState } from 'react';
import { useStudio } from '@/lib/store';
import { Settings as SettingsIcon, LogOut, Gem } from 'lucide-react';

export default function Settings() {
  const { apiKey, setApiKey, gems } = useStudio();
  const [showSettings, setShowSettings] = useState(false);
  const [tempKey, setTempKey] = useState(apiKey);
  const [showKey, setShowKey] = useState(false);

  if (!apiKey) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800 flex items-center justify-center p-4">
        <div className="bg-slate-800 border border-slate-700 rounded-lg p-8 max-w-md w-full">
          <div className="text-center mb-6">
            <div className="text-4xl mb-3">🎬</div>
            <h1 className="text-2xl font-bold text-white">Multimedia Studio</h1>
            <p className="text-slate-400 text-sm mt-2">AI-powered image, video & chat generation</p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white mb-2">API Key</label>
              <p className="text-xs text-slate-400 mb-2">
                Get your API key from{' '}
                <a
                  href="https://promptchan.com/settings"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-400 hover:text-blue-300"
                >
                  promptchan.com/settings
                </a>
              </p>
              <input
                type="password"
                value={tempKey}
                onChange={(e) => setTempKey(e.target.value)}
                placeholder="sk_..."
                className="w-full px-4 py-2 bg-slate-900 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-400"
              />
            </div>

            <button
              onClick={() => {
                if (tempKey.trim()) {
                  setApiKey(tempKey);
                }
              }}
              disabled={!tempKey.trim()}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white font-semibold py-2 rounded transition-colors"
            >
              Connect Studio
            </button>

            <p className="text-xs text-slate-400 text-center">
              Purchase gems at{' '}
              <a
                href="https://promptchan.com/gems"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:text-blue-300"
              >
                promptchan.com/gems
              </a>
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="flex items-center gap-3">
        {gems > 0 && (
          <div className="flex items-center gap-2 px-3 py-1 bg-slate-700 rounded text-sm">
            <Gem className="w-4 h-4 text-yellow-400" />
            <span className="text-white font-semibold">{gems}</span>
          </div>
        )}
        <button
          onClick={() => setShowSettings(true)}
          className="p-2 hover:bg-slate-700 rounded transition-colors"
        >
          <SettingsIcon className="w-5 h-5 text-slate-400" />
        </button>
      </div>

      {showSettings && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 max-w-md w-full">
            <h2 className="text-lg font-bold text-white mb-4">Settings</h2>

            <div className="space-y-4 mb-6">
              <div>
                <label className="block text-sm font-medium text-white mb-2">API Key</label>
                <div className="flex gap-2">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={tempKey}
                    onChange={(e) => setTempKey(e.target.value)}
                    className="flex-1 px-3 py-2 bg-slate-900 border border-slate-600 rounded text-white text-sm focus:outline-none focus:border-blue-400"
                  />
                  <button
                    onClick={() => setShowKey(!showKey)}
                    className="px-3 py-2 hover:bg-slate-700 rounded text-slate-400 text-sm"
                  >
                    {showKey ? '🙈' : '👁️'}
                  </button>
                </div>
              </div>

              {gems >= 0 && (
                <div>
                  <label className="block text-sm font-medium text-white mb-2">Gems Balance</label>
                  <div className="px-3 py-2 bg-slate-900 border border-slate-600 rounded text-white flex items-center gap-2">
                    <Gem className="w-4 h-4 text-yellow-400" />
                    <span>{gems}</span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => {
                  if (tempKey.trim()) {
                    setApiKey(tempKey);
                  }
                  setShowSettings(false);
                }}
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 rounded transition-colors"
              >
                Save
              </button>
              <button
                onClick={() => {
                  setApiKey('');
                  setShowSettings(false);
                }}
                className="flex-1 bg-red-600 hover:bg-red-700 text-white font-semibold py-2 rounded transition-colors flex items-center justify-center gap-2"
              >
                <LogOut className="w-4 h-4" />
                Logout
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
