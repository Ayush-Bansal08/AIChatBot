import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
dotenv.config({ path: './.env' }); // load env vars from project root

import axios from 'axios';
const app = express();
app.use(cors(
    {
        origin: process.env.CORS_ORIGIN, // allow only the frontend to access the backend, CORS_ORIGIN is defined in the .env file, it should be the url of the frontend
        credentials: true
    }
))
app.use(express.json()); // to send json data to the frontend

app.post('/api/chat', async (req,res)=>{
   try {
     const userMessage = req.body.message;
     console.log("User message: ", userMessage);
      
     const response = await axios.post("http://localhost:8000/chat", {message: userMessage}); // get the response form python backend
     console.log("AI response: ", response.data.reply);
         res.json({reply: response.data.reply}); // backend response to the frontend from python gemeini model
         
 
   } catch (error) {
        console.error("Error in /api/chat: ", error);
        res.status(500).json({error: "An error occurred while processing your request."});
    
   }
})





export {app};