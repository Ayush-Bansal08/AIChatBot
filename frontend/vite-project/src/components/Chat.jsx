import { useState } from "react";
import axios from "axios";
function Chat() {

    const [message, setMessage] = useState(""); // to set the messages from the user and the AI\
    const [chat,setchat] = useState([]); // to store the chat history, it will be an array of objects, each object will have two properties, message and sender
    const sendMessage = async () => {
        try {
            if(message.trim() === ""){
                console.log("message can not be empty");
                alert("message can not be empty");
                return;
            } // if the message is empty, do not send it
            setchat([...chat, {message: message, sender: "user"}]); // add the user's message to the chat history
            const response = await axios.post("http://localhost:5000/api/chat", {message}); // send the message to the backend, now backend has the text message from the user and it will process it and send back the response from the AI
            console.log("message sent to backend and the message is",message)
            setchat([...chat, {message: response.data.reply, sender: "ai"}]); // add the AI's response to the chat history, response.data.reply is the reply from the AI that we get from the backend
            setMessage(""); // clear the input field after sending the message
            
        } catch (error) {
            console.error("Error sending message to backend: ", error);
             alert("An error occurred while sending your message. Please try again later.");
            
        }
    }


  return(
    <div>
        <h1>Chat with AI</h1>
         <div>
        {chat.map((msg, index) => (
          <p key={index}>
            <b>{msg.sender}:</b> {msg.message}
          </p>
        ))}
      </div>
        <input type="text" value={message} onChange={(e)=>setMessage(e.target.value)} placeholder="Type your message here..." />
        <button onClick={sendMessage}>Send</button>
        </div>

  )

}

export default Chat;