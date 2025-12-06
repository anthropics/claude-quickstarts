import React from "react";
import { X, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import Image from "next/image";

interface FilePreviewProps {
  file: {
    base64: string;
    fileName: string;
    mediaType: string;
    isText?: boolean;
  };
  onRemove?: () => void;
  size?: "small" | "large";
}

const FilePreview: React.FC<FilePreviewProps> = ({
  file,
  onRemove,
  size = "large",
}) => {
  const isImage = file.mediaType.startsWith("image/");
  const fileExtension = file.fileName.split(".").pop()?.toLowerCase() || "";

  const truncatedName =
    file.fileName.length > 7
      ? `${file.fileName.slice(0, 7)}...${file.fileName.slice(
          file.fileName.lastIndexOf("."),
        )}`
      : file.fileName;

  const imageUrl = isImage
    ? `data:${file.mediaType};base64,${file.base64}`
    : "";

  if (size === "small") {
    return (
      <Badge variant="secondary" className="gap-2 py-1 px-3">
        {isImage ? (
          <div className="relative w-4 h-4">
            <Image
              src={imageUrl}
              alt={file.fileName}
              className="object-cover rounded"
              fill
              sizes="16px"
              unoptimized
            />
          </div>
        ) : (
          <FileText className="w-4 h-4" />
        )}
        <span className="text-xs">{truncatedName}</span>
      </Badge>
    );
  }

  return (
    <div className="relative inline-flex items-center rounded-lg border bg-card text-card-foreground shadow-sm w-16 h-16">
      {isImage ? (
        <div className="relative w-full h-full">
          <Image
            src={imageUrl}
            alt={file.fileName}
            className="object-cover rounded-lg"
            fill
            sizes="64px"
            unoptimized
          />
        </div>
      ) : (
        <div className="w-full h-full flex flex-col items-center justify-center bg-muted rounded-lg">
          <FileText className="w-6 h-6 mb-1" />
          <span className="text-xs font-medium uppercase">{fileExtension}</span>
        </div>
      )}
      {onRemove && (
        <button
          onClick={(e) => {
            e.preventDefault();
            onRemove();
          }}
          className="absolute -top-2 -right-2 rounded-full bg-destructive p-1 text-destructive-foreground hover:bg-destructive/90"
        >
          <X className="h-3 w-3" />
        </button>
      )}
    </div>
  );
};

export default FilePreview;
