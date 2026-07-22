"use client";

import { useEffect, useState, useRef } from "react";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Search, FileText, FileSpreadsheet, Image as ImageIcon, CheckCircle2, Clock, UploadCloud, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, DocumentResponse } from "@/lib/api";

export default function KnowledgeHub() {
  const [documents, setDocuments] = useState<DocumentResponse[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Fetch documents periodically
  useEffect(() => {
    let timeoutId: NodeJS.Timeout;
    
    const fetchDocs = async () => {
      try {
        const docs = await api.getDocuments();
        setDocuments(docs.sort((a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime()));
        setError(null);
      } catch (err: any) {
        setError("Failed to fetch documents. Backend might be unavailable.");
      }
      
      // Determine if we need to poll (if any doc is not Ready/Failed)
      const isProcessing = documents.some(d => d.status !== 'Ready' && d.status !== 'Failed');
      timeoutId = setTimeout(fetchDocs, isProcessing ? 2000 : 5000);
    };
    
    fetchDocs();
    return () => clearTimeout(timeoutId);
  }, []);

  const handleUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.pdf')) {
      setError("Only PDF files are supported for the MVP.");
      return;
    }

    setIsUploading(true);
    setError(null);
    try {
      await api.uploadDocument(file);
      // Immediate refresh after upload starts
      const docs = await api.getDocuments();
      setDocuments(docs.sort((a, b) => new Date(b.uploaded_at).getTime() - new Date(a.uploaded_at).getTime()));
    } catch (err: any) {
      setError(err.message || "Failed to upload document.");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const getIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch(ext) {
      case "pdf": return <FileText className="h-4 w-4 text-rose-500" />;
      case "docx": return <FileText className="h-4 w-4 text-blue-500" />;
      case "xlsx": return <FileSpreadsheet className="h-4 w-4 text-emerald-500" />;
      case "png":
      case "jpg": return <ImageIcon className="h-4 w-4 text-amber-500" />;
      default: return <FileText className="h-4 w-4 text-zinc-500" />;
    }
  };

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6">
      
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-2xl font-bold text-zinc-100">Knowledge Hub</h2>
          <p className="text-sm text-zinc-400">Manage and explore ingested operational documents.</p>
        </div>
        <div className="flex gap-2">
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-zinc-500" />
            <Input 
              placeholder="Search documents..." 
              className="pl-9 bg-zinc-900 border-zinc-800 text-zinc-100 focus-visible:ring-cyan-500"
            />
          </div>
          <input 
            type="file" 
            ref={fileInputRef} 
            onChange={handleUpload} 
            accept=".pdf" 
            className="hidden" 
          />
          <Button 
            className="bg-cyan-600 hover:bg-cyan-700 text-white" 
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
          >
            {isUploading ? (
              <Clock className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <UploadCloud className="w-4 h-4 mr-2" />
            )}
            Upload Document
          </Button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-md flex items-center gap-3 text-red-400">
          <AlertCircle className="w-5 h-5" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      <Card className="bg-zinc-900 border-zinc-800">
        <CardHeader>
          <CardTitle className="text-zinc-100">Ingested Assets</CardTitle>
          <CardDescription className="text-zinc-400">Documents transformed into the NeuroFab Knowledge Graph.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border border-zinc-800 overflow-hidden">
            <Table>
              <TableHeader className="bg-zinc-950/50">
                <TableRow className="border-zinc-800 hover:bg-transparent">
                  <TableHead className="text-zinc-400">Document</TableHead>
                  <TableHead className="text-zinc-400">Uploaded</TableHead>
                  <TableHead className="text-zinc-400">Duration</TableHead>
                  <TableHead className="text-zinc-400">Status</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {documents.length === 0 ? (
                  <TableRow className="border-zinc-800 hover:bg-transparent">
                    <TableCell colSpan={4} className="text-center text-zinc-500 py-8">
                      No documents found. Upload a PDF to begin ingestion.
                    </TableCell>
                  </TableRow>
                ) : (
                  documents.map((doc) => (
                    <TableRow key={doc.id} className="border-zinc-800 hover:bg-zinc-800/50">
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-3">
                          {getIcon(doc.filename)}
                          <span className="text-zinc-300">{doc.filename}</span>
                        </div>
                      </TableCell>
                      <TableCell className="text-zinc-500">
                        {new Date(doc.uploaded_at).toLocaleString()}
                      </TableCell>
                      <TableCell className="text-zinc-500">
                        {doc.processing_duration ? `${doc.processing_duration.toFixed(1)}s` : '-'}
                      </TableCell>
                      <TableCell>
                        {doc.status === 'Ready' ? (
                          <Badge variant="outline" className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 flex w-fit gap-1 items-center">
                            <CheckCircle2 className="w-3 h-3" /> Indexed
                          </Badge>
                        ) : doc.status === 'Failed' ? (
                          <Badge variant="outline" className="bg-rose-500/10 text-rose-400 border-rose-500/20 flex w-fit gap-1 items-center">
                            <AlertCircle className="w-3 h-3" /> Failed
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="bg-amber-500/10 text-amber-400 border-amber-500/20 flex w-fit gap-1 items-center">
                            <Clock className="w-3 h-3 animate-pulse" /> {doc.status}
                          </Badge>
                        )}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
