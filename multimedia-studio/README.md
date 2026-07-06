# 🎬 Multimedia Studio

A complete multimedia creation platform powered by the Promptchan API. Generate stunning images and videos with AI, and chat with intelligent companions.

## Features

- **🖼️ Image Generation**: Create beautiful images with customizable styles, emotions, and filters
- **🎥 Video Generation**: Generate dynamic videos with async processing and status tracking
- **💬 AI Chat**: Engage with AI companions with customizable personalities
- **📚 Gallery**: Organized gallery for your generated content
- **⚙️ Settings**: Easy API key management and gems tracking

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn
- Promptchan API key from [promptchan.com/settings](https://promptchan.com/settings)

### Installation

```bash
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Build

```bash
npm run build
npm start
```

## API Configuration

1. Sign up at [promptchan.com/signup](https://promptchan.com/signup)
2. Generate an API key at [promptchan.com/settings](https://promptchan.com/settings)
3. Purchase gems at [promptchan.com/gems](https://promptchan.com/gems)
4. Enter your API key in the studio settings

## Usage

### Image Generation

1. Navigate to the **Images** tab
2. Enter a detailed prompt
3. Customize style, emotion, and filter
4. Select quality level (Ultra/Extreme/Max)
5. Click **Generate Image**

### Video Generation

1. Navigate to the **Videos** tab
2. Enter a video description
3. Choose style and aspect ratio
4. Enable audio if needed
5. Click **Generate Video**
6. Video will start processing and track progress

### Chat

1. Navigate to the **Chat** tab
2. Optionally set a character name and personality
3. Start chatting with the AI companion
4. Messages are saved in the conversation history

## Project Structure

```
multimedia-studio/
├── app/
│   ├── layout.tsx       # Root layout
│   └── page.tsx         # Main studio page
├── components/
│   ├── Settings.tsx     # API key and settings
│   ├── ImageGenerator.tsx
│   ├── VideoGenerator.tsx
│   ├── ChatInterface.tsx
│   └── Gallery.tsx      # Gallery view
├── lib/
│   ├── promptchan-client.ts  # API client
│   └── store.ts              # Zustand store
├── styles/
│   └── globals.css      # Tailwind styles
└── public/
```

## Technologies

- **Next.js 14**: Full-stack React framework
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Zustand**: State management
- **Axios**: HTTP client

## API Endpoints

All requests require the `x-api-key` header with your Promptchan API key.

### Image Generation
`POST /api/external/create`

### Video Generation
- Submit: `POST /api/external/video_v4/submit`
- Status: `GET /api/external/video_v4/status_with_logs/{request_id}`
- Result: `GET /api/external/video_v4/result/{request_id}`

### Chat
`POST /api/external/chat`

## Billing

Each image/video generation costs gems:
- **Image**: 1 gem per generation (+ extra gems for Extreme/Max quality)
- **Video**: Varies by style and parameters
- **Chat**: Included in your account access

## License

MIT
