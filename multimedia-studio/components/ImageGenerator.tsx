'use client';

import { useState } from 'react';
import { useStudio } from '@/lib/store';
import { createClient } from '@/lib/promptchan-client';
import { Loader, Zap } from 'lucide-react';

const STYLES = [
  'Cinematic',
  'Anime',
  'Hyperreal',
  'Photo XL+',
  'Hyperreal XL+',
  'Render XL+',
  'Anime XL',
  'Cinematic XL',
];

const EMOTIONS = [
  'Default',
  'Smiling',
  'Laughing',
  'Angry',
  'Scared',
  'Orgasm Face',
];

const FILTERS = ['Default', 'Cinematic', 'Studio', 'Noir Movie', 'VHS', 'Pixel Art'];

export default function ImageGenerator() {
  const { apiKey, addImage, setGems } = useStudio();
  const [prompt, setPrompt] = useState('');
  const [style, setStyle] = useState('Cinematic');
  const [emotion, setEmotion] = useState('Default');
  const [filter, setFilter] = useState('Default');
  const [quality, setQuality] = useState<'Ultra' | 'Extreme' | 'Max'>('Ultra');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const client = createClient(apiKey);
      const result = await client.generateImage({
        prompt,
        style,
        emotion,
        filter,
        quality,
        image_size: '768x512',
      });

      if (result.image) {
        addImage({
          id: Math.random().toString(36).substr(2, 9),
          url: `data:image/png;base64,${result.image}`,
          prompt,
          timestamp: Date.now(),
          params: { style, emotion, filter, quality },
        });

        if (result.gems !== undefined) {
          setGems(result.gems);
        }

        setPrompt('');
      }
    } catch (err: any) {
      setError(err.message || 'Failed to generate image');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6">
      <h2 className="text-lg font-bold text-white mb-4">🖼️ Image Generator</h2>

      <div className="space-y-4">
        {/* Prompt */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Prompt</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="Describe the image you want to generate..."
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
            {STYLES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        {/* Emotion */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Emotion</label>
          <select
            value={emotion}
            onChange={(e) => setEmotion(e.target.value)}
            disabled={loading}
            className="w-full px-4 py-2 bg-slate-900 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
          >
            {EMOTIONS.map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </div>

        {/* Filter */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Filter</label>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            disabled={loading}
            className="w-full px-4 py-2 bg-slate-900 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
          >
            {FILTERS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </select>
        </div>

        {/* Quality */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">Quality</label>
          <select
            value={quality}
            onChange={(e) => setQuality(e.target.value as 'Ultra' | 'Extreme' | 'Max')}
            disabled={loading}
            className="w-full px-4 py-2 bg-slate-900 border border-slate-600 rounded text-white focus:outline-none focus:border-blue-400 disabled:opacity-50"
          >
            <option value="Ultra">Ultra (1 gem)</option>
            <option value="Extreme">Extreme (2 gems)</option>
            <option value="Max">Max (3 gems)</option>
          </select>
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
              Generating...
            </>
          ) : (
            <>
              <Zap className="w-4 h-4" />
              Generate Image
            </>
          )}
        </button>
      </div>
    </div>
  );
}
