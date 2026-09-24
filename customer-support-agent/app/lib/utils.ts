import {
  BedrockAgentRuntimeClient,
  RetrieveCommand,
  RetrieveCommandInput,
} from "@aws-sdk/client-bedrock-agent-runtime";
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

console.log("🔑 Have AWS AccessKey?", !!process.env.BAWS_ACCESS_KEY_ID);
console.log("🔑 Have AWS Secret?", !!process.env.BAWS_SECRET_ACCESS_KEY);

const bedrockClient = new BedrockAgentRuntimeClient({
  customUserAgent: [["claude-quickstarts", "bedrock-kb"]],
  region: "us-east-1", // Make sure this matches your Bedrock region
  credentials: {
    accessKeyId: process.env.BAWS_ACCESS_KEY_ID!,
    secretAccessKey: process.env.BAWS_SECRET_ACCESS_KEY!,
  },
});

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export type KnowledgeBaseType = "VECTOR" | "MANAGED";

export interface RAGSource {
  id: string;
  fileName: string;
  snippet: string;
  score: number;
}

export async function retrieveContext(
  query: string,
  knowledgeBaseId: string,
  n: number = 3,
  knowledgeBaseType?: KnowledgeBaseType,
): Promise<{
  context: string;
  isRagWorking: boolean;
  ragSources: RAGSource[];
}> {
  try {
    if (!knowledgeBaseId) {
      console.error("knowledgeBaseId is not provided");
      return {
        context: "",
        isRagWorking: false,
        ragSources: [],
      };
    }

    // Determine KB type from parameter, env var, or default to VECTOR
    const resolvedType: KnowledgeBaseType =
      knowledgeBaseType ||
      (process.env.KNOWLEDGE_BASE_TYPE as KnowledgeBaseType) ||
      "VECTOR";

    // Build retrieval configuration based on knowledge base type
    const retrievalConfiguration =
      resolvedType === "MANAGED"
        ? { managedSearchConfiguration: { numberOfResults: n } }
        : { vectorSearchConfiguration: { numberOfResults: n } };

    const input: RetrieveCommandInput = {
      knowledgeBaseId: knowledgeBaseId,
      retrievalQuery: { text: query },
      retrievalConfiguration: retrievalConfiguration as any,
    };

    console.log(
      `🔍 Using ${resolvedType} knowledge base retrieval for KB: ${knowledgeBaseId}`,
    );

    // Try AgenticRetrieveStream for MANAGED KBs (intelligent multi-step retrieval)
    // Toggle: USE_AGENTIC_RETRIEVAL=false to disable, GENERATE_RESPONSE=true for answer generation
    const useAgentic = (process.env.USE_AGENTIC_RETRIEVAL ?? "true") === "true";
    const generateResponse = (process.env.GENERATE_RESPONSE ?? "false") === "true";
    if (resolvedType === "MANAGED" && useAgentic) {
      try {
        const agenticCommand = {
          messages: [{ content: { text: query }, role: "user" }],
          retrievers: [
            {
              configuration: {
                knowledgeBase: {
                  knowledgeBaseId,
                  retrievalOverrides: { maxNumberOfResults: n },
                },
              },
            },
          ],
          agenticRetrieveConfiguration: {
            foundationModelType: "MANAGED",
            rerankingModelType: "MANAGED",
          },
          generateResponse,
        };
        const agenticResponse = await (bedrockClient as any).send(
          new ((await import("@aws-sdk/client-bedrock-agent-runtime")) as any).AgenticRetrieveStreamCommand(agenticCommand),
        );
        // Process agentic stream results
        const agenticResults: any[] = [];
        let generatedAnswer = "";
        for await (const event of agenticResponse.stream || []) {
          if (event.result?.results) {
            agenticResults.push(...event.result.results);
          }
          if (event.result?.messages) {
            for (const msg of event.result.messages) {
              if (msg.content?.text) {
                generatedAnswer += msg.content.text;
              }
            }
          }
        }
        if (generatedAnswer) {
          // Use the generated cited answer as context
          const ragSources: RAGSource[] = agenticResults
            .filter((res: any) => res.content?.text)
            .map((result: any, index: number) => ({
              id: `agentic-chunk-${index}`,
              fileName: result.location?.s3Location?.uri?.split("/").pop() || `Source-${index}`,
              snippet: result.content.text,
              score: result.score || 0,
            }))
            .slice(0, 3);
          console.log("✅ Agentic retrieval with generated response");
          return { context: generatedAnswer, isRagWorking: true, ragSources };
        }
        if (agenticResults.length > 0) {
          const ragSources: RAGSource[] = agenticResults
            .filter((res: any) => res.content?.text)
            .map((result: any, index: number) => ({
              id: `agentic-chunk-${index}`,
              fileName: result.location?.s3Location?.uri?.split("/").pop() || `Source-${index}`,
              snippet: result.content.text,
              score: result.score || 0,
            }))
            .slice(0, 3);
          const context = agenticResults
            .filter((res: any) => res.content?.text)
            .map((res: any) => res.content.text)
            .join("\n\n");
          console.log("✅ Agentic retrieval successful with managed reranking");
          return { context, isRagWorking: true, ragSources };
        }
      } catch (e) {
        console.log("⚠️ AgenticRetrieveStream not available, falling back to Retrieve:", (e as Error).message);
      }
    }

    // Fallback: standard Retrieve API
    const command = new RetrieveCommand(input);
    const response = await bedrockClient.send(command);

    // Parse results
    const rawResults = response?.retrievalResults || [];
    const ragSources: RAGSource[] = rawResults
      .filter((res: any) => res.content && res.content.text)
      .map((result: any, index: number) => {
        const uri = result?.location?.s3Location?.uri || "";
        const fileName = uri.split("/").pop() || `Source-${index}.txt`;

        return {
          id:
            result.metadata?.["x-amz-bedrock-kb-chunk-id"] || `chunk-${index}`,
          fileName: fileName.replace(/_/g, " ").replace(".txt", ""),
          snippet: result.content?.text || "",
          score: result.score || 0,
        };
      })
      .slice(0, 1);

    console.log("🔍 Parsed RAG Sources:", ragSources); // Debug log

    const context = rawResults
      .filter((res: any) => res.content && res.content.text)
      .map((res: any) => res.content.text)
      .join("\n\n");

    return {
      context,
      isRagWorking: true,
      ragSources,
    };
  } catch (error) {
    console.error("RAG Error:", error);
    return { context: "", isRagWorking: false, ragSources: [] };
  }
}
