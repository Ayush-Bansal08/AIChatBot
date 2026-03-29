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
     const question = req.body.message; // get the message from the frontend
     console.log("User message: ", question);
     const video_id = req.body.video_id; // get the video id from the frontend, it is optional, if the user does not want to provide the video id, it will be undefined
     console.log("Video ID: ", video_id);
      
     const response = await axios.post("http://localhost:8000/chat", {question: question, video_id: video_id}); // get the response form python backend
     console.log("AI response: ", response.data.answer);
         res.json({reply: response.data.answer}); // backend response to the frontend from python gemeini model

         
 
   } catch (error) {  
        console.error("Error in /api/chat: ", error);
        res.status(500).json({error: "An error occurred while processing your request."});
    
   }
})





export {app};