import { create } from 'zustand';

export interface ImageItem {
  id: string;
  url: string;
  prompt: string;
  timestamp: number;
  params: any;
}

export interface VideoItem {
  id: string;
  requestId: string;
  prompt: string;
  timestamp: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress?: number;
  urls?: string[];
  params: any;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

interface StudioStore {
  apiKey: string;
  setApiKey: (key: string) => void;

  images: ImageItem[];
  addImage: (image: ImageItem) => void;
  clearImages: () => void;

  videos: VideoItem[];
  addVideo: (video: VideoItem) => void;
  updateVideo: (id: string, updates: Partial<VideoItem>) => void;
  clearVideos: () => void;

  chatHistory: ChatMessage[];
  addChatMessage: (message: ChatMessage) => void;
  clearChat: () => void;

  gems: number;
  setGems: (gems: number) => void;

  activeTab: 'images' | 'videos' | 'chat';
  setActiveTab: (tab: 'images' | 'videos' | 'chat') => void;
}

export const useStudio = create<StudioStore>((set) => ({
  apiKey: typeof window !== 'undefined' ? localStorage.getItem('promptchan_api_key') || '' : '',
  setApiKey: (key) => {
    set({ apiKey: key });
    if (typeof window !== 'undefined') {
      localStorage.setItem('promptchan_api_key', key);
    }
  },

  images: [],
  addImage: (image) => set((state) => ({ images: [image, ...state.images] })),
  clearImages: () => set({ images: [] }),

  videos: [],
  addVideo: (video) => set((state) => ({ videos: [video, ...state.videos] })),
  updateVideo: (id, updates) =>
    set((state) => ({
      videos: state.videos.map((v) => (v.id === id ? { ...v, ...updates } : v)),
    })),
  clearVideos: () => set({ videos: [] }),

  chatHistory: [],
  addChatMessage: (message) => set((state) => ({ chatHistory: [...state.chatHistory, message] })),
  clearChat: () => set({ chatHistory: [] }),

  gems: 0,
  setGems: (gems) => set({ gems }),

  activeTab: 'images',
  setActiveTab: (tab) => set({ activeTab: tab }),
}));
