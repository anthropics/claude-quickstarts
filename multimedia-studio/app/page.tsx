'use client';

import { useEffect, useState } from 'react';
import { useStudio } from '@/lib/store';
import Settings from '@/components/Settings';
import ImageGenerator from '@/components/ImageGenerator';
import VideoGenerator from '@/components/VideoGenerator';
import ChatInterface from '@/components/ChatInterface';
import Gallery from '@/components/Gallery';

export default function Home() {
  const [mounted, setMounted] = useState(false);
  const { activeTab, setActiveTab, apiKey } = useStudio();

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  if (!apiKey) {
    return <Settings />;
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 to-slate-800">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <header className="border-b border-slate-700 bg-slate-900/50 backdrop-blur sticky top-0 z-40">
          <div className="px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="text-3xl">🎬</div>
              <div>
                <h1 className="text-2xl font-bold text-white">Multimedia Studio</h1>
                <p className="text-sm text-slate-400">Complete multimedia creation platform</p>
              </div>
            </div>
            <Settings />
          </div>
        </header>

        {/* Navigation Tabs */}
        <div className="border-b border-slate-700 bg-slate-800/50 backdrop-blur">
          <div className="max-w-7xl mx-auto px-6">
            <div className="flex gap-1">
              {(['images', 'videos', 'chat'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-6 py-4 font-semibold transition-colors border-b-2 ${
                    activeTab === tab
                      ? 'text-blue-400 border-blue-400'
                      : 'text-slate-400 border-transparent hover:text-slate-300'
                  }`}
                >
                  {tab === 'images' && '🖼️ Images'}
                  {tab === 'videos' && '🎥 Videos'}
                  {tab === 'chat' && '💬 Chat'}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Content */}
        <main className="px-6 py-8">
          {activeTab === 'images' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-1">
                <ImageGenerator />
              </div>
              <div className="lg:col-span-2">
                <Gallery type="images" />
              </div>
            </div>
          )}

          {activeTab === 'videos' && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              <div className="lg:col-span-1">
                <VideoGenerator />
              </div>
              <div className="lg:col-span-2">
                <Gallery type="videos" />
              </div>
            </div>
          )}

          {activeTab === 'chat' && <ChatInterface />}
        </main>
      </div>
    </div>
  );
}
