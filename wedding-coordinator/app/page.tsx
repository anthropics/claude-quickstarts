"use client";

import { useState } from "react";
import WeddingParamsForm from "@/components/WeddingParamsForm";
import ChatWindow from "@/components/ChatWindow";
import { WeddingParams } from "@/types/wedding";

export default function Home() {
  const [params, setParams] = useState<WeddingParams | null>(null);

  if (!params) {
    return <WeddingParamsForm onSubmit={setParams} />;
  }

  return <ChatWindow params={params} onReset={() => setParams(null)} />;
}
