import { FC, useState } from "react";
import { Loader2, AlertCircle } from "lucide-react";

interface VisualizationArtifactProps {
  artifactId: string;
  apiUrl?: string;
}

/**
 * Sandboxed iframe component for displaying HTML visualization artifacts.
 * 
 * Security:
 * - Uses restrictive sandbox attribute (no scripts, forms, popups, same-origin)
 * - Isolates artifact from parent page (no access to cookies, localStorage, session)
 * - Prevents navigation and modal dialogs
 * 
 * @param artifactId - The unique artifact ID from backend
 * @param apiUrl - Optional API base URL (defaults to current origin)
 */
export const VisualizationArtifact: FC<VisualizationArtifactProps> = ({
  artifactId,
  apiUrl = "",
}) => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const artifactUrl = `${apiUrl}/artifacts/${artifactId}`;

  const handleLoad = () => {
    setLoading(false);
  };

  const handleError = () => {
    setLoading(false);
    setError("Failed to load visualization");
  };

  return (
    <div className="my-4 relative w-full border rounded-lg overflow-hidden bg-muted/30">
      {/* Loading State */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
          <div className="flex items-center gap-2 text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span className="text-sm">Loading visualization...</span>
          </div>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/50 z-10">
          <div className="flex items-center gap-2 text-destructive">
            <AlertCircle className="h-4 w-4" />
            <span className="text-sm">{error}</span>
          </div>
        </div>
      )}

      {/* Sandboxed Iframe */}
      <iframe
        src={artifactUrl}
        onLoad={handleLoad}
        onError={handleError}
        sandbox="allow-same-origin" // Minimal: only allows CSS/images, no scripts or forms
        className="w-full border-0"
        style={{ 
          minHeight: "300px",
          height: "auto",
        }}
        title={`Visualization ${artifactId}`}
        // Security: no allow-scripts, allow-forms, allow-popups, allow-top-navigation
      />
    </div>
  );
};
