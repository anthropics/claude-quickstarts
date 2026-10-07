import axios, { AxiosInstance } from 'axios';

const BASE_URL = 'https://prod.aicloudnetservices.com';

export interface ImageGenerationRequest {
  prompt: string;
  style?: string;
  filter?: string;
  emotion?: string;
  detail?: number;
  seed?: number;
  quality?: 'Ultra' | 'Extreme' | 'Max';
  creativity?: number;
  image_size?: '512x512' | '512x768' | '768x512';
  negative_prompt?: string;
  restore_faces?: boolean;
  age_slider?: number;
  weight_slider?: number;
  breast_slider?: number;
  ass_slider?: number;
  poses?: any;
}

export interface VideoGenerationRequest {
  aspect?: 'Portrait' | 'Landscape' | 'Square';
  audioEnabled?: boolean;
  prompt: string;
  style?: string;
  weight_slider?: number;
  breast_slider?: number;
  ass_slider?: number;
  age_slider?: number;
  seed?: number;
  pose?: string;
}

export interface ChatRequest {
  message: string;
  characterData?: {
    name?: string;
    personality?: string;
    scenario?: string;
    sexuality?: string;
    openness?: number;
    emotions?: number;
    age?: number;
    gender?: string;
  };
  chatHistory?: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
  isRoleplay?: boolean;
  redo?: boolean;
  userName?: string;
}

export class PromptchanClient {
  private client: AxiosInstance;
  private apiKey: string;

  constructor(apiKey: string) {
    this.apiKey = apiKey;
    this.client = axios.create({
      baseURL: BASE_URL,
      headers: {
        'x-api-key': apiKey,
        'Content-Type': 'application/json',
      },
    });
  }

  async generateImage(params: ImageGenerationRequest) {
    try {
      const response = await this.client.post('/api/external/create', params);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || 'Failed to generate image');
    }
  }

  async submitVideo(params: VideoGenerationRequest) {
    try {
      const response = await this.client.post('/api/external/video_v4/submit', params);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || 'Failed to submit video generation');
    }
  }

  async getVideoStatus(requestId: string) {
    try {
      const response = await this.client.get(
        `/api/external/video_v4/status_with_logs/${requestId}`
      );
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || 'Failed to get video status');
    }
  }

  async getVideoResult(requestId: string) {
    try {
      const response = await this.client.get(`/api/external/video_v4/result/${requestId}`);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || 'Failed to get video result');
    }
  }

  async chat(params: ChatRequest) {
    try {
      const response = await this.client.post('/api/external/chat', params);
      return response.data;
    } catch (error: any) {
      throw new Error(error.response?.data?.error || 'Failed to chat');
    }
  }
}

export const createClient = (apiKey: string) => new PromptchanClient(apiKey);
