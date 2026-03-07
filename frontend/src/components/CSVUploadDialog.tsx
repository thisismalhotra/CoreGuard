"use client";

import { useState, useRef } from "react";
import { Upload, FileSpreadsheet, CheckCircle2, AlertCircle, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { api } from "@/lib/api";

type UploadResult = {
  created: number;
  updated: number;
  total_processed: number;
  errors: { row: number; part_id?: string; error: string }[];
  error_count: number;
};

export function CSVUploadDialog() {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const reset = () => {
    setFile(null);
    setResult(null);
    setError(null);
  };

  const handleFile = (f: File) => {
    setResult(null);
    setError(null);
    if (!f.name.toLowerCase().endsWith(".csv")) {
      setError("Only .csv files are accepted");
      return;
    }
    if (f.size > 2 * 1024 * 1024) {
      setError("File too large (max 2 MB)");
      return;
    }
    setFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const data = await api.uploadDemandForecast(file);
      setResult(data);
      setFile(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        setOpen(v);
        if (!v) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="border-input text-muted-foreground hover:text-foreground hover:border-foreground/30 gap-1.5"
        >
          <Upload className="h-3.5 w-3.5" />
          Upload CSV
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Upload Demand Forecast</DialogTitle>
          <DialogDescription>
            Upload a CSV with columns: <code className="text-xs bg-muted px-1 py-0.5 rounded">part_id</code>,{" "}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">forecast_qty</code>. Optional:{" "}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">period</code>,{" "}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">source</code>,{" "}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">confidence_level</code>,{" "}
            <code className="text-xs bg-muted px-1 py-0.5 rounded">notes</code>.
          </DialogDescription>
        </DialogHeader>

        {/* Drop zone */}
        {!result && (
          <div
            className={`border-2 border-dashed rounded-lg p-6 text-center transition-colors cursor-pointer ${
              dragOver
                ? "border-blue-400 bg-blue-950/20"
                : "border-border hover:border-muted-foreground/50"
            }`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              const dropped = e.dataTransfer.files[0];
              if (dropped) handleFile(dropped);
            }}
            onClick={() => inputRef.current?.click()}
          >
            <input
              ref={inputRef}
              type="file"
              accept=".csv"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleFile(f);
                e.target.value = "";
              }}
            />
            <FileSpreadsheet className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
            {file ? (
              <div className="flex items-center justify-center gap-2">
                <span className="text-sm font-medium">{file.name}</span>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                  className="text-muted-foreground hover:text-foreground"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">
                  Drag & drop a CSV file, or click to browse
                </p>
                <p className="text-xs text-muted-foreground mt-1">Max 2 MB</p>
              </>
            )}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 text-sm text-red-400 bg-red-950/30 border border-red-700/50 rounded-lg px-3 py-2">
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-green-400">
              <CheckCircle2 className="h-4 w-4" />
              Upload complete
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="bg-muted rounded-lg p-2">
                <div className="text-lg font-bold">{result.created}</div>
                <div className="text-xs text-muted-foreground">Created</div>
              </div>
              <div className="bg-muted rounded-lg p-2">
                <div className="text-lg font-bold">{result.updated}</div>
                <div className="text-xs text-muted-foreground">Updated</div>
              </div>
              <div className="bg-muted rounded-lg p-2">
                <div className={`text-lg font-bold ${result.error_count > 0 ? "text-red-400" : ""}`}>
                  {result.error_count}
                </div>
                <div className="text-xs text-muted-foreground">Errors</div>
              </div>
            </div>
            {result.errors.length > 0 && (
              <div className="max-h-32 overflow-y-auto text-xs space-y-1">
                {result.errors.map((e, i) => (
                  <div
                    key={i}
                    className="text-red-400 bg-red-950/20 rounded px-2 py-1"
                  >
                    Row {e.row}
                    {e.part_id && ` (${e.part_id})`}: {e.error}
                  </div>
                ))}
              </div>
            )}
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={reset}
            >
              Upload Another
            </Button>
          </div>
        )}

        {/* Upload button */}
        {file && !result && (
          <Button
            className="w-full"
            onClick={handleUpload}
            disabled={uploading}
          >
            {uploading ? "Uploading..." : "Upload"}
          </Button>
        )}
      </DialogContent>
    </Dialog>
  );
}
