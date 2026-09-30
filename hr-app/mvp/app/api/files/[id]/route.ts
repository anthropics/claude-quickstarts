import { NextRequest, NextResponse } from "next/server";
import { getApiUser } from "@/lib/session";
import { readStoredFile } from "@/lib/uploads";

/** Authenticated download/stream. */
export async function GET(_req: NextRequest, { params }: { params: { id: string } }) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const stored = readStoredFile(Number(params.id));
  if (!stored) return NextResponse.json({ error: "File not found" }, { status: 404 });

  return new NextResponse(new Uint8Array(stored.data), {
    headers: {
      "Content-Type": stored.meta.mime,
      "Content-Disposition": `inline; filename="${stored.meta.original_name.replace(/"/g, "")}"`,
      "Content-Length": String(stored.meta.size_bytes),
      "Cache-Control": "private, max-age=3600",
    },
  });
}
