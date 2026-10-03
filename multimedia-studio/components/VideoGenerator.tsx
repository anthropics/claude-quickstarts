'use client';

import { useState, useEffect } from 'react';
import { useStudio } from '@/lib/store';
import { createClient } from '@/lib/promptchan-client';
import { Loader, Zap } from 'lucide-react';

const VIDEO_STYLES = [
  'Real',
  'Photo XL+',
  'Hyperreal XL+',
  'Cinematic XL',
  'Anime XL',
  'Render XL+',
];

const ASPECTS = ['Portrait', 'Landscape', 'Square'];

export default function VideoGenerator() {
  const { apiKey, addVideo, updateVideo, videos } = useStudio();
  const [prompt, setPrompt] = useState('');
  const [style, setStyle] = useState('Real');
  const [aspect, setAspect] = useState<'Portrait' | 'Landscape' | 'Square'>('Portrait');
  const [audioEnabled, setAudioEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [pollingIntervals, setPollingIntervals] = useState<{ [key: string]: NodeJS.Timeout }>({});

  useEffect(() => {
    const videoClient = createClient(apiKey);
    const activeVideos = videos.filter((v) => v.status === 'pending' || v.status === 'processing');

    activeVideos.forEach((video) => {
      if (!pollingIntervals[video.requestId]) {
        const interval = setInterval(async () => {
          try {
            const status = await videoClient.getVideoStatus(video.requestId);
            updateVideo(video.id, {
              progress: status.progress || 0,
            });

            if (status.progress === 100) {
              const result = await videoClient.getVideoResult(video.requestId);
              updateVideo(video.id, {
                status: 'completed',
                urls: result.video,
              });
              clearInterval(interval);
            }
          } catch (err: any) {
            updateVideo(video.id, {
              status: 'failed',
            });
            clearInterval(interval);
          }
        }, 3000);

        setPollingIntervals((prev) => ({
          ...prev,
          [video.requestId]: interval,
        }));
      }
    });

    return () => {
      Object.values(pollingIntervals).forEach(clearInterval);
    };
  }, [apiKey, videos, updateVideo, pollingIntervals]);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const client = createClient(apiKey);
      const result = await client.submitVideo({
        prompt,
        style,
        aspect,
        audioEnabled,
      });

      const videoId = Math.random().toString(36).substr(2, 9);
      addVideo({
        id: videoId,
        requestId: result.request_id,
        prompt,
        timestamp: Date.now(),
        status: 'pending',
        progress: 0,
        params: { style, aspect, audioEnabled },
      });

      setPrompt('');
    } catch (err: any) {
      setError(err.message || 'Failed to submit video');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-bold text-white mb-4">🎥 Video Generator</h2>

      <div className="space-y-4">
        {/* Prompt */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Prompt</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe the video you want to generate..."
            disabled={loading}
            className="w-full px-4 py-3 bg-slate-900 border border-slate-600 rounded text-white placeholder-slate-500 focus:outline-none focus:border-blue-400 disabled:opacity-50 resize-none h-24"
          />
        </div>

        {/* Style */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Style</label>
          <select
            value={style}
            onChange={(e) => setStyle(e.target.value)}
            disabled={loading}
            className="w-full px-4 py-2 bg-slate-900 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
          >
            {VIDEO_STYLES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Aspect Ratio */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Aspect Ratio</label>
          <select
            value={aspect}
            onChange={(e) => setAspect(e.target.value as any)}
            disabled={loading}
            className="w-full px-4 py-2 bg-slate-900 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
          >
            {ASPECTS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>

        {/* Audio */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="audioEnabled"
            checked={audioEnabled}
            onChange={(e) => setAudioEnabled(e.target.checked)}
            disabled={loading}
            className="w-4 h-4 rounded"
          />
          <label htmlFor="audioEnabled" className="text-sm font-medium text-slate-300">
            Enable Audio
          </label>
        </div>

        {/* Error */}
        {error && <div className="p-3 bg-red-900/50 border border-red-700 rounded text-red-200 text-sm">{error}</div>}

        {/* Generate Button */}
        <button
          onClick={handleGenerate}
          disabled={loading || !prompt.trim()}
          className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 text-white font-semibold py-3 rounded transition-colors flex items-center justify-center gap-2"
        >
          {loading ? (
            <>
              <Loader className="w-4 h-4 animate-spin" />
              Submitting...
            </>
          ) : (
            <>
              <Zap className="w-4 h-4" />
              Generate Video
            </>
          )}
        </button>
      </div>
    </div>
  );
}
