import {app} from "./app.js";
import dotenv from 'dotenv';
dotenv.config({ path: './.env' }); // load env vars from project root

app.listen(process.env.PORT, ()=>{
    console.log(`Server is running on port ${process.env.PORT}`);
})
