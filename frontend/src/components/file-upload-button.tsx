import { FC, useRef, useState } from "react";
import { Upload, X, FileIcon, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { TooltipIconButton } from "@/components/tooltip-icon-button";
import { dreamFarmAPI } from "@/services/api";

interface FileUploadButtonProps {
  onFileUploaded?: (fileId: string, filename: string) => void;
  onError?: (error: string) => void;
  disabled?: boolean;
}

/**
 * File upload button component for code interpreter attachments.
 * Accepts CSV, Excel, JSON, TXT, PDF, and image files up to 30MB.
 */
export const FileUploadButton: FC<FileUploadButtonProps> = ({
  onFileUploaded,
  onError,
  disabled = false,
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadedFile, setUploadedFile] = useState<{ id: string; name: string } | null>(null);

  const handleClick = () => {
    if (!disabled && !uploading) {
      fileInputRef.current?.click();
    }
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Validate file size (30MB limit)
    const MAX_SIZE = 30 * 1024 * 1024; // 30MB
    if (file.size > MAX_SIZE) {
      const errorMsg = `File too large. Maximum size is 30MB. Your file: ${(file.size / (1024 * 1024)).toFixed(1)}MB`;
      onError?.(errorMsg);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    // Validate file type
    const allowedExtensions = ['.csv', '.xlsx', '.xls', '.json', '.txt', '.pdf', '.png', '.jpg', '.jpeg', '.gif'];
    const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
    if (!allowedExtensions.includes(fileExtension)) {
      const errorMsg = `Unsupported file type: ${fileExtension}. Allowed: ${allowedExtensions.join(', ')}`;
      onError?.(errorMsg);
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    setUploading(true);
    try {
      const result = await dreamFarmAPI.uploadFile(file);
      setUploadedFile({ id: result.file_id, name: result.filename });
      onFileUploaded?.(result.file_id, result.filename);
    } catch (error: any) {
      const errorMsg = error.message || 'Failed to upload file';
      onError?.(errorMsg);
      console.error('File upload error:', error);
    } finally {
      setUploading(false);
      // Reset input so the same file can be uploaded again if needed
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleRemove = () => {
    setUploadedFile(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="flex items-center gap-2">
      <input
        ref={fileInputRef}
        type="file"
        accept=".csv,.xlsx,.xls,.json,.txt,.pdf,.png,.jpg,.jpeg,.gif"
        onChange={handleFileChange}
        className="hidden"
        disabled={disabled || uploading}
      />

      {!uploadedFile && (
        <TooltipIconButton
          tooltip={uploading ? "Uploading..." : "Upload file"}
          variant="ghost"
          size="icon"
          className={cn(
            "my-2.5 size-8 p-2 transition-opacity ease-in",
            (disabled || uploading) && "opacity-50 cursor-not-allowed"
          )}
          onClick={handleClick}
          disabled={disabled || uploading}
        >
          {uploading ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Upload className="h-4 w-4" />
          )}
        </TooltipIconButton>
      )}

      {uploadedFile && (
        <div className="flex items-center gap-2 rounded-md bg-muted px-2 py-1 text-xs">
          <FileIcon className="h-3 w-3" />
          <span className="max-w-[150px] truncate">{uploadedFile.name}</span>
          <button
            onClick={handleRemove}
            className="hover:text-destructive transition-colors"
            type="button"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      )}
    </div>
  );
};
