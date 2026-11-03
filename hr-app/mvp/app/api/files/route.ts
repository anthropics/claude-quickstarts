import { NextRequest, NextResponse } from "next/server";
import { getApiUser } from "@/lib/session";
import { saveUpload, UploadError } from "@/lib/uploads";
import { logAudit } from "@/lib/db";

/** Multipart upload endpoint. Returns { id, original_name } for linking. */
export async function POST(req: NextRequest) {
  const user = getApiUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!file || typeof file === "string") {
    return NextResponse.json({ error: "No file provided (multipart field 'file')" }, { status: 400 });
  }

  try {
    const buffer = Buffer.from(await file.arrayBuffer());
    const stored = saveUpload(buffer, file.name, file.type, user.id);
    logAudit(user.id, "file.upload", "file", stored.id, file.name);
    return NextResponse.json({ id: stored.id, original_name: stored.original_name }, { status: 201 });
  } catch (e) {
    if (e instanceof UploadError) return NextResponse.json({ error: e.message }, { status: 400 });
    throw e;
  }
}
