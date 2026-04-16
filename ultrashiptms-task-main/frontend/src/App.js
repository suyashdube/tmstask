import { useState, useRef } from "react";
import "@/App.css";
import axios from "axios";
import { 
  TrayArrowUp, 
  PaperPlaneTilt, 
  BracketsCurly,
  Circle,
  FileText,
  ChatCircleDots
} from "@phosphor-icons/react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [document, setDocument] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [asking, setAsking] = useState(false);
  const [extractedData, setExtractedData] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const fileInputRef = useRef(null);

  const handleFileUpload = async (file) => {
    if (!file) return;

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const response = await axios.post(`${API}/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setDocument(response.data);
      setMessages([]);
      setExtractedData(null);
    } catch (error) {
      console.error("Upload error:", error);
      alert("Error uploading document: " + (error.response?.data?.detail || error.message));
    } finally {
      setUploading(false);
    }
  };

  const handleAskQuestion = async () => {
    if (!question.trim() || !document) return;

    const userMessage = { type: "user", text: question };
    setMessages((prev) => [...prev, userMessage]);
    setAsking(true);
    const currentQuestion = question;
    setQuestion("");

    try {
      const response = await axios.post(`${API}/ask`, {
        question: currentQuestion,
        document_id: document.document_id,
      });

      const aiMessage = {
        type: "ai",
        text: response.data.answer,
        confidence: response.data.confidence_score,
        sources: response.data.source_chunks,
      };
      setMessages((prev) => [...prev, aiMessage]);
    } catch (error) {
      console.error("Question error:", error);
      const errorMessage = {
        type: "ai",
        text: "❌ Error processing question: " + (error.response?.data?.detail || error.message),
        confidence: 0,
        sources: [],
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setAsking(false);
    }
  };

  const handleExtract = async () => {
    if (!document) return;

    setExtracting(true);
    try {
      const response = await axios.post(`${API}/extract`, {
        document_id: document.document_id,
      });
      setExtractedData(response.data);
    } catch (error) {
      console.error("Extract error:", error);
      alert("Error extracting data: " + (error.response?.data?.detail || error.message));
    } finally {
      setExtracting(false);
    }
  };

  const getConfidenceStyle = (confidence) => {
    if (confidence >= 0.7) return "bg-green-50 text-green-600 border-green-200";
    if (confidence >= 0.4) return "bg-yellow-50 text-yellow-600 border-yellow-200";
    return "bg-red-50 text-red-600 border-red-200";
  };

  return (
    <div className="h-screen w-full flex flex-col md:flex-row bg-surface text-text_main overflow-hidden">
      {/* Left Panel - Upload & Extract */}
      <div className="lg:w-1/4 border-r border-border bg-card_background flex flex-col h-full overflow-y-auto">
        <div className="p-6 border-b border-border">
          <h2 className="text-2xl tracking-tight font-bold mb-1">Document AI</h2>
          <p className="text-xs tracking-[0.2em] uppercase font-bold text-text_muted">Logistics TMS</p>
        </div>

        {/* Upload Zone */}
        <div className="p-6 flex-1 flex flex-col">
          <div className="mb-6">
            <label className="text-xs tracking-[0.2em] uppercase font-bold text-text_muted mb-3 block">
              Upload Document
            </label>
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => handleFileUpload(e.target.files[0])}
              accept=".pdf,.docx,.txt"
              className="hidden"
            />
            <div
              data-testid="upload-dropzone"
              onClick={() => fileInputRef.current?.click()}
              className="border-dashed border-2 border-border hover:border-primary bg-surface transition-colors p-8 flex flex-col items-center justify-center text-center cursor-pointer min-h-[160px]"
            >
              <TrayArrowUp size={48} weight="duotone" className="text-text_muted mb-3" />
              <p className="text-sm font-medium text-text_main mb-1">
                {uploading ? "Processing..." : "Click to upload"}
              </p>
              <p className="text-xs text-text_muted">PDF, DOCX, or TXT</p>
            </div>
          </div>

          {/* Document Status */}
          {document && (
            <div data-testid="doc-status-indicator" className="mb-6">
              <div className="px-2 py-1 text-xs font-mono uppercase tracking-widest border border-primary text-primary bg-primary/5 flex items-center gap-2">
                <Circle size={8} weight="fill" />
                <span>Ready</span>
              </div>
              <div className="mt-2 text-xs text-text_muted">
                <FileText size={14} className="inline mr-1" />
                {document.filename}
              </div>
              <div className="text-xs text-text_muted">
                {document.chunk_count} chunks
              </div>
            </div>
          )}

          {/* Extract Button */}
          {document && (
            <div className="mt-auto">
              <button
                data-testid="extract-json-button"
                onClick={handleExtract}
                disabled={extracting}
                className="w-full border border-primary text-primary hover:bg-primary hover:text-white transition-all p-3 font-mono text-sm uppercase flex items-center justify-center gap-2 disabled:opacity-50"
              >
                <BracketsCurly size={20} weight="bold" />
                {extracting ? "Extracting..." : "Extract JSON"}
              </button>

              {/* JSON Output */}
              {extractedData && (
                <div className="mt-4">
                  <div className="text-xs tracking-[0.2em] uppercase font-bold text-text_muted mb-2">
                    Confidence: {(extractedData.confidence_score * 100).toFixed(0)}%
                  </div>
                  <pre className="bg-text_main text-surface p-4 font-mono text-xs overflow-x-auto max-h-[300px] overflow-y-auto">
                    {JSON.stringify(extractedData.extracted_data, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Center Panel - Chat */}
      <div className="lg:w-1/2 border-r border-border bg-background flex flex-col h-full">
        {/* Chat Header */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center gap-2">
            <ChatCircleDots size={24} weight="duotone" className="text-primary" />
            <h3 className="text-lg tracking-tight font-semibold">Ask Questions</h3>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {!document && (
            <div className="text-center text-text_muted text-sm mt-20">
              Upload a document to start asking questions
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx}>
              {msg.type === "user" ? (
                <div className="bg-surface border border-border p-4 ml-auto max-w-[85%] text-sm">
                  {msg.text}
                </div>
              ) : (
                <div className="bg-background border-l-4 border-primary p-4 mr-auto max-w-[95%] text-sm shadow-sm relative">
                  <div
                    data-testid="confidence-score"
                    className={`px-2 py-0.5 text-[10px] font-mono uppercase inline-flex items-center gap-1 absolute top-2 right-2 border ${getConfidenceStyle(
                      msg.confidence
                    )}`}
                  >
                    {(msg.confidence * 100).toFixed(0)}%
                  </div>
                  <div className="pr-16">{msg.text}</div>
                  {msg.sources && msg.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-border">
                      <div className="text-xs text-text_muted mb-2 uppercase tracking-wide">Sources:</div>
                      {msg.sources.map((source, sidx) => (
                        <div key={sidx} className="text-xs text-text_muted mt-1 pl-2 border-l-2 border-border">
                          {source.substring(0, 150)}...
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}

          {asking && (
            <div className="bg-background border-l-4 border-primary p-4 mr-auto max-w-[95%] text-sm shadow-sm">
              <div className="flex items-center gap-2 text-text_muted">
                <Circle size={8} weight="fill" className="animate-pulse" />
                Thinking...
              </div>
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="p-4 border-t border-border bg-background flex gap-2">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyPress={(e) => e.key === "Enter" && handleAskQuestion()}
            placeholder="Ask about the document..."
            disabled={!document || asking}
            className="flex-1 bg-surface border border-border rounded-none focus:ring-2 focus:ring-primary focus:border-primary transition-all px-4 py-2 text-sm disabled:opacity-50"
          />
          <button
            onClick={handleAskQuestion}
            disabled={!document || asking || !question.trim()}
            className="bg-primary text-white rounded-none hover:bg-primary_hover transition-colors font-medium px-4 py-2 flex items-center justify-center gap-2 disabled:opacity-50"
          >
            <PaperPlaneTilt size={20} weight="fill" />
          </button>
        </div>
      </div>

      {/* Right Panel - Source Viewer */}
      <div className="lg:w-1/4 bg-card_background flex flex-col h-full">
        <div className="p-6 border-b border-border">
          <h3 className="text-lg tracking-tight font-semibold">Document Source</h3>
        </div>
        <div data-testid="source-viewer" className="flex-1 overflow-y-auto p-4 bg-surface font-mono text-xs leading-loose">
          {!document && (
            <div className="text-text_muted text-center mt-10">No document loaded</div>
          )}
          {document && (
            <div className="text-text_main whitespace-pre-wrap">
              Document processed with {document.chunk_count} chunks.
              <br />
              <br />
              Ask questions to see relevant sources highlighted here.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default App;