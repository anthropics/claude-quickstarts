import { getDb } from "./db";
import { randomUUID } from "crypto";
import fs from "fs";
import path from "path";

/**
 * Local-disk file storage behind a stable interface (swap the fs calls for
 * S3/R2 later without touching callers). Files live in uploads/ (gitignored),
 * metadata in the files table; access is always through the authenticated
 * /api/files/[id] route.
 */

const UPLOAD_DIR = path.join(process.cwd(), "uploads");
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024; // 5 MB

export const ALLOWED_MIME: Record<string, string> = {
  "application/pdf": ".pdf",
  "image/png": ".png",
  "image/jpeg": ".jpg",
  "application/msword": ".doc",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
};

export interface StoredFile {
  id: number;
  storage_name: string;
  original_name: string;
  mime: string;
  size_bytes: number;
}

export function saveUpload(buffer: Buffer, originalName: string, mime: string, uploadedBy: number | null): StoredFile {
  if (buffer.length > MAX_UPLOAD_BYTES) throw new UploadError(`File exceeds ${MAX_UPLOAD_BYTES / 1024 / 1024} MB limit`);
  const ext = ALLOWED_MIME[mime];
  if (!ext) throw new UploadError(`File type not allowed (${mime}). Allowed: PDF, PNG, JPG, DOC, DOCX`);

  fs.mkdirSync(UPLOAD_DIR, { recursive: true });
  const storageName = `${randomUUID()}${ext}`;
  fs.writeFileSync(path.join(UPLOAD_DIR, storageName), buffer);

  const res = getDb()
    .prepare("INSERT INTO files (storage_name, original_name, mime, size_bytes, uploaded_by) VALUES (?, ?, ?, ?, ?)")
    .run(storageName, originalName.slice(0, 255), mime, buffer.length, uploadedBy);
  return {
    id: Number(res.lastInsertRowid),
    storage_name: storageName,
    original_name: originalName,
    mime,
    size_bytes: buffer.length,
  };
}

export function readStoredFile(fileId: number): { meta: StoredFile; data: Buffer } | null {
  const meta = getDb().prepare("SELECT * FROM files WHERE id = ?").get(fileId) as StoredFile | undefined;
  if (!meta) return null;
  const full = path.join(UPLOAD_DIR, meta.storage_name);
  if (!fs.existsSync(full)) return null;
  return { meta, data: fs.readFileSync(full) };
}

export class UploadError extends Error {}
