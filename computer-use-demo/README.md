# Anthropic Computer Use Demo

> [!NOTE]
> Now featuring support for the latest Claude models! Available models: Claude Opus 4.7 (claude-opus-4-7), Claude Opus 4.6 (claude-opus-4-6), Claude Opus 4.5 (claude-opus-4-5), Claude Sonnet 4.6 (claude-sonnet-4-6), Claude Sonnet 4.5 (claude-sonnet-4-5), and Claude Haiku 4.5 (claude-haiku-4-5-20251001). These models bring next-generation capabilities with the updated str_replace_based_edit_tool that replaces the previous str_replace_editor tool. The undo_edit command has been removed in this latest version for a more streamlined experience.

> [!CAUTION]
> Computer use is a beta feature. Please be aware that computer use poses unique risks that are distinct from standard API features or chat interfaces. These risks are heightened when using computer use to interact with the internet. To minimize risks, consider taking precautions such as:
>
> 1. Use a dedicated virtual machine or container with minimal privileges to prevent direct system attacks or accidents.
> 2. Avoid giving the model access to sensitive data, such as account login information, to prevent information theft.
> 3. Limit internet access to an allowlist of domains to reduce exposure to malicious content.
> 4. Ask a human to confirm decisions that may result in meaningful real-world consequences as well as any tasks requiring affirmative consent, such as accepting cookies, executing financial transactions, or agreeing to terms of service.
>
> In some circumstances, Claude will follow commands found in content even if it conflicts with the user's instructions. For example, instructions on webpages or contained in images may override user instructions or cause Claude to make mistakes. We suggest taking precautions to isolate Claude from sensitive data and actions to avoid risks related to prompt injection.
>
> Finally, please inform end users of relevant risks and obtain their consent prior to enabling computer use in your own products.

This repository helps you get started with computer use on Claude, with reference implementations of:

- Build files to create a Docker container with all necessary dependencies
- A computer use agent loop using the Claude API, Bedrock, or Vertex to access Claude Opus 4.7, Opus 4.6, Opus 4.5, Sonnet 4.6, Sonnet 4.5, and Haiku 4.5 models
- Anthropic-defined computer use tools
- A **FastAPI backend** that exposes chat/message APIs and streams assistant progress in real time over WebSocket, plus a lightweight HTML/JS frontend with an embedded VNC desktop panel

Please use [this form](https://forms.gle/BT1hpBrqDPDUrCqo7) to provide feedback on the quality of the model responses, the API itself, or the quality of the documentation - we cannot wait to hear from you!

> [!IMPORTANT]
> The Beta API used in this reference implementation is subject to change. Please refer to the [API release notes](https://docs.claude.com/en/release-notes/api) for the most up-to-date information.

> [!IMPORTANT]
> The container runs a single shared Xvfb desktop. The backend supports multiple concurrent chats safely (per-chat locks, async task isolation, a global desktop lock serialising tool actions), but logically those chats still share one screen. Production deployments should run one container per user.

## Quickstart

### Docker Compose (recommended)

```bash
export ANTHROPIC_API_KEY=%your_api_key%
docker compose up --build
```

Then open **http://localhost:8000** for the chat + desktop view.

### `docker run`

#### Claude API

> [!TIP]
> You can find your API key in the [Claude Console](https://console.anthropic.com/).

```bash
export ANTHROPIC_API_KEY=%your_api_key%
docker run \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -v $HOME/.anthropic:/home/computeruse/.anthropic \
    -p 5900:5900 \
    -p 8000:8000 \
    -p 6080:6080 \
    -it ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest
```

Once the container is running, see the [Accessing the demo app](#accessing-the-demo-app) section below for instructions on how to connect to the interface.

#### Bedrock

> [!TIP]
> To use the new Claude 3.7 Sonnet on Bedrock, you first need to [request model access](https://docs.aws.amazon.com/bedrock/latest/userguide/model-access-modify.html).

```bash
export AWS_PROFILE=<your_aws_profile>
docker run \
    -e API_PROVIDER=bedrock \
    -e AWS_PROFILE=$AWS_PROFILE \
    -e AWS_REGION=us-west-2 \
    -v $HOME/.aws:/home/computeruse/.aws \
    -v $HOME/.anthropic:/home/computeruse/.anthropic \
    -p 5900:5900 \
    -p 8000:8000 \
    -p 6080:6080 \
    -it ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest
```

#### Vertex

```bash
docker build . -t computer-use-demo
gcloud auth application-default login
export VERTEX_REGION=%your_vertex_region%
export VERTEX_PROJECT_ID=%your_vertex_project_id%
docker run \
    -e API_PROVIDER=vertex \
    -e CLOUD_ML_REGION=$VERTEX_REGION \
    -e ANTHROPIC_VERTEX_PROJECT_ID=$VERTEX_PROJECT_ID \
    -v $HOME/.config/gcloud/application_default_credentials.json:/home/computeruse/.config/gcloud/application_default_credentials.json \
    -p 5900:5900 \
    -p 8000:8000 \
    -p 6080:6080 \
    -it computer-use-demo
```

## Accessing the demo app

- **Chat + desktop view**: [http://localhost:8000](http://localhost:8000)
- **API docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Desktop only (noVNC)**: [http://localhost:6080/vnc.html](http://localhost:6080/vnc.html)
- **Raw VNC**: `vnc://localhost:5900`

The container stores settings and chat history in `~/.anthropic/`:

- `api_key`, `system_prompt` — user-editable config
- `db.sqlite` — persistent chat and message history

Mount this directory (`-v $HOME/.anthropic:/home/computeruse/.anthropic`) to persist these between container runs.

## API surface

The backend exposes a JSON API under `/api/`. Full OpenAPI docs at `/docs`. Highlights:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/system` | Available providers / models / tool versions |
| `GET`/`PUT` | `/api/system/api-key` | API key persisted to `~/.anthropic/api_key` |
| `GET`/`PUT` | `/api/system/base-url` | Anthropic base URL override |
| `GET`/`PUT` | `/api/system/system-prompt` | System-prompt suffix |
| `POST` | `/api/chats` | Create a chat |
| `GET` | `/api/chats` | List chats |
| `GET` | `/api/chats/{id}` | Chat + full message history |
| `DELETE` | `/api/chats/{id}` | Cancel running turn + delete chat |
| `POST` | `/api/chats/{id}/messages` | Send a user message (fire-and-forget; stream progress over WS) |
| `POST` | `/api/chats/{id}/cancel` | Cancel the currently-running turn |
| `GET` | `/api/chats/{id}/images/{image_id}` | Stored screenshot bytes |
| `WS` | `/api/chats/{id}/ws?since_seq=N` | Real-time event stream; resumes via `since_seq` on reconnect |

### WebSocket event envelope

```json
{
  "v": 1,
  "chat_id": "…",
  "turn_id": "…",
  "seq": 42,
  "ts": "2026-04-23T12:00:00Z",
  "type": "text_delta",
  "data": { "block_index": 0, "text": "Hello" }
}
```

Event types: `turn_started`, `text_delta`, `thinking_delta`, `input_json_delta`, `block_start`, `assistant_block`, `tool_result`, `api_meta`, `turn_complete`, `error`, `cancelled`, `pong`.

## Remote deployment

This image **ships no authentication or TLS** and the noVNC server does not require a password. For any deployment reachable from outside your machine:

1. Terminate TLS and enforce authentication in a reverse proxy in front of port 8000.
2. **Do not** expose ports 5900 or 6080 publicly — keep them on a private network or behind the same authenticating proxy.
3. Prefer one container per user; concurrent chats within a single container share the desktop.

## Screen size

Environment variables `WIDTH` and `HEIGHT` set the virtual screen size:

```bash
docker run \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -v $HOME/.anthropic:/home/computeruse/.anthropic \
    -p 5900:5900 -p 8000:8000 -p 6080:6080 \
    -e WIDTH=1920 \
    -e HEIGHT=1080 \
    -it ghcr.io/anthropics/anthropic-quickstarts:computer-use-demo-latest
```

We do not recommend sending screenshots in resolutions above [XGA/WXGA](https://en.wikipedia.org/wiki/Display_resolution_standards#XGA) to avoid issues related to [image resizing](https://docs.claude.com/en/docs/build-with-claude/vision#evaluate-image-size). Relying on the image resizing behavior in the API will result in lower model accuracy and slower performance than implementing scaling in your tools directly. The `computer` tool implementation in this project demonstrates how to scale both images and coordinates from higher resolutions to the suggested resolutions.

When implementing computer use yourself, we recommend using XGA resolution (1024x768):

- For higher resolutions: scale the image down to XGA and let the model interact with this scaled version, then map the coordinates back to the original resolution proportionally.
- For lower resolutions or smaller devices (e.g. mobile devices): add black padding around the display area until it reaches 1024x768.

## Development

```bash
./setup.sh                                    # venv + dev deps + pre-commit
docker build . -t computer-use-demo:local     # (optional) rebuild image
export ANTHROPIC_API_KEY=%your_api_key%
docker run \
    -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
    -v $(pwd)/computer_use_demo:/home/computeruse/computer_use_demo/ \
    -v $HOME/.anthropic:/home/computeruse/.anthropic \
    -p 5900:5900 -p 8000:8000 -p 6080:6080 \
    -it computer-use-demo:local
```

### Local testing

```bash
ruff check . && ruff format .
pyright
pytest
```
