# Bedrock Managed Knowledge Base Support

## Changes
- Added per-KB type configuration via `KNOWLEDGE_BASE_TYPE` environment variable
- Retrieval helper selects `managedSearchConfiguration` or `vectorSearchConfiguration` based on KB type
- Added `KNOWLEDGE_BASE_TYPE` to `.env.example` and configuration documentation
- Added agentic retrieval path for enhanced answer quality in support scenarios

## Design
- VECTOR is the default for backward compatibility; MANAGED via `KNOWLEDGE_BASE_TYPE=MANAGED` env var or per-KB `type` field
- Per-KB type config allows mixed deployments (some KBs managed, some vector)
- AgenticRetrieveStream used for agentic retrieval when enabled
- Backward compatible: existing deployments continue working without changes

## API Shapes
- KB Creation: `type: MANAGED` + `managedKnowledgeBaseConfiguration.embeddingModelType: MANAGED`
- Retrieval: `managedSearchConfiguration` (not `vectorSearchConfiguration`)
- Agentic: `AgenticRetrieveStream` with `foundationModelType: MANAGED`, `rerankingModelType: MANAGED`

## Configuration
| Variable | Description | Default |
|---|---|---|
| KNOWLEDGE_BASE_TYPE | MANAGED or VECTOR | VECTOR |
| USE_AGENTIC_RETRIEVAL | Enable agentic retrieval | true |
| KNOWLEDGE_BASE_ID | Customer support KB ID | (required) |

## SDK Requirements
- boto3 >= 1.43 for managed search and agentic retrieval
