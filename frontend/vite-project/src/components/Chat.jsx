import { useEffect, useRef, useState } from "react";
import axios from "axios";

const QUICK_PROMPTS = [
  "Give me a five line summary",
  "What are the key takeaways?",
  "Explain this video in simple words",
  "What is the video mainly about?"
];

function Chat() {

    const [message, setMessage] = useState(""); // to set the messages from the user and the AI\
    const [video_id, setVideoId] = useState(""); // to set the video id from the user, it is optional, if the user does not want to provide the video id, it will be an empty string
    const [chat,setchat] = useState([]); // to store the chat history, it will be an array of objects, each object will have two properties, message and sender
  const [activeVideoId, setActiveVideoId] = useState("");
    const [isSending, setIsSending] = useState(false);
    const [uiError, setUiError] = useState("");
    const chatWindowRef = useRef(null);

    useEffect(() => {
      if (chatWindowRef.current) {
        chatWindowRef.current.scrollTop = chatWindowRef.current.scrollHeight;
      }
    }, [chat, isSending]);

    const handleQuickPrompt = (promptText) => {
      setMessage(promptText);
      setUiError("");
    };

    const handleSetVideoId = () => {
      const trimmed = video_id.trim();
      if (!trimmed) {
        setUiError("Enter a valid video ID before setting it.");
        return;
      }
      setActiveVideoId(trimmed);
      setVideoId("");
      setUiError("");
    };

    const handleClearVideoId = () => {
      setActiveVideoId("");
      setUiError("");
    };

    const handleMessageKeyDown = (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    };

    const copyMessage = async (text) => {
      try {
        await navigator.clipboard.writeText(text);
      } catch (error) {
        console.error("Copy failed:", error);
      }
    };

    const formatDuration = (ms) => {
      if (typeof ms !== "number") return "-";
      if (ms < 1000) return `${ms} ms`;
      return `${(ms / 1000).toFixed(2)} s`;
    };

    const sendMessage = async () => {
        if (isSending) {
            return;
        }

        try {
            setUiError("");
          const typedVideoId = video_id.trim();
          const effectiveVideoId = typedVideoId || activeVideoId;

            if(message.trim() === ""){
                console.log("message can not be empty");
                setUiError("Message cannot be empty.");
                return;
            } // if the message is empty, do not send it
          if(!effectiveVideoId){
                console.log("Video ID can not be empty");
            setUiError("Set a YouTube Video ID once before asking questions.");
                return;
            }

          if (typedVideoId) {
            setActiveVideoId(typedVideoId);
          }

            setIsSending(true);
            
            setchat(prev => [...prev, {message: message, sender: "user"}]); // add the user's message to the chat history
            console.log("message added to chat history and the message is",message)
          console.log("video id is", effectiveVideoId)
          const response = await axios.post("http://localhost:5000/api/chat", {message,video_id: effectiveVideoId}); // send the message to the backend, now backend has the text message from the user and it will process it and send back the response from the AI
            console.log("message sent to backend and the message is",message)
            const aiReply = response.data.answer || response.data.reply;
            const process = Array.isArray(response.data.process) ? response.data.process : [];
            setchat(prev => [...prev, {message: aiReply, sender: "ai", process}]); // add the AI's response and process trace to chat history
            setMessage(""); // clear the input field after sending the message
          setVideoId(""); // clear only manual input; activeVideoId remains for follow-up questions

        } catch (error) {
            console.error("Error sending message to backend: ", error);
             const backendMessage = error.response?.data?.error || error.response?.data?.detail;
       setUiError(backendMessage || "An error occurred while sending your message. Please try again later.");
            
    } finally {
      setIsSending(false);
        }
    }


  return(
    <div className="chat-shell">
      <div className="chat-modal-overlay">
        <div className="chat-bg-orb chat-bg-orb-left" aria-hidden="true" />
        <div className="chat-bg-orb chat-bg-orb-right" aria-hidden="true" />

        <section className="chat-card chat-modal" role="dialog" aria-modal="true" aria-label="AI chat window">
        <header className="chat-header">
          <p className="chat-kicker">AI Video Assistant</p>
          <h1>Chat with AI</h1>
          <p className="chat-subtitle">
            Ask questions about any YouTube video transcript and get focused answers.
          </p>
        </header>

        <div className="chat-toolbar">
          <div className="chat-toolbar-title">Quick prompts</div>
          <div className="chat-quick-list">
            {QUICK_PROMPTS.map((promptText) => (
              <button
                key={promptText}
                className="chat-quick-chip"
                onClick={() => handleQuickPrompt(promptText)}
                type="button"
              >
                {promptText}
              </button>
            ))}
          </div>
        </div>

        <div className="chat-video-memory">
          <div className="chat-video-state">
            <span className="chat-video-label">Current Video</span>
            <span className="chat-video-value">{activeVideoId || "Not set"}</span>
          </div>
          <button type="button" className="chat-video-clear" onClick={handleClearVideoId} disabled={!activeVideoId || isSending}>
            Clear
          </button>
        </div>

        {uiError && <div className="chat-error-banner">{uiError}</div>}

        <div className="chat-window" role="log" aria-live="polite" ref={chatWindowRef}>
          {chat.length === 0 ? (
            <div className="chat-empty">
              <p>Start the conversation</p>
              <span>Enter a video ID and ask your first question.</span>
            </div>
          ) : (
            chat.map((msg, index) => (
              <article key={index} className={`chat-bubble ${msg.sender === "user" ? "chat-bubble-user" : "chat-bubble-ai"}`}>
                <div className="chat-bubble-head">
                  <p className="chat-bubble-label">{msg.sender === "user" ? "You" : "AI"}</p>
                  {msg.sender === "ai" && (
                    <button className="chat-copy-btn" type="button" onClick={() => copyMessage(msg.message)}>
                      Copy
                    </button>
                  )}
                </div>
                <p className="chat-bubble-text">{msg.message}</p>
                {msg.sender === "ai" && Array.isArray(msg.process) && msg.process.length > 0 && (
                  <details className="chat-process" open>
                    <summary>How AI generated this answer</summary>
                    <ul className="chat-process-list">
                      {msg.process.map((step, stepIndex) => (
                        <li key={`${index}-${stepIndex}`} className="chat-process-item">
                          <div className="chat-process-title">
                            <span>{step.step || "Step"}</span>
                            <span>{formatDuration(step.duration_ms)}</span>
                          </div>
                          {step.details && <p className="chat-process-details">{step.details}</p>}
                        </li>
                      ))}
                    </ul>
                  </details>
                )}
              </article>
            ))
          )}

          {isSending && (
            <article className="chat-bubble chat-bubble-ai chat-bubble-thinking">
              <div className="chat-bubble-head">
                <p className="chat-bubble-label">AI</p>
              </div>
              <div className="chat-thinking-dots" aria-label="AI is thinking">
                <span />
                <span />
                <span />
              </div>
            </article>
          )}
        </div>

        <div className="chat-form">
          <textarea
            value={message}
            onChange={(e)=>setMessage(e.target.value)}
            onKeyDown={handleMessageKeyDown}
            placeholder="Type your message here..."
            className="chat-input chat-message-input"
            rows={2}
            maxLength={500}
          />
          <input
            type="text"
            value={video_id}
            onChange={(e)=>setVideoId(e.target.value)}
            placeholder={activeVideoId ? "Type a new video ID to switch" : "Enter YouTube video ID"}
            className="chat-input chat-video-input"
            maxLength={20}
          />
          <button type="button" className="chat-set-video-btn" onClick={handleSetVideoId} disabled={isSending || !video_id.trim()}>
            Set Video
          </button>
          <button onClick={sendMessage} className="chat-send-btn" disabled={isSending}>
            {isSending ? "Sending..." : "Send"}
          </button>
        </div>

        <div className="chat-footer-meta">
          <span>{message.length}/500</span>
          <span>Press Enter to send</span>
        </div>
        </section>
      </div>
    </div>

  )

}

export default Chat;