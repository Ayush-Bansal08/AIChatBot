from fastapi import FastAPI
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

model = ChatGoogleGenerativeAI(
   model="gemini-2.5-flash",
    temperature=0.7,
    max_tokens=500
)

class ChatRequest(BaseModel):
    message: str

@app.post("/chat") ## server is listening to this endpoint for incoming chat messages
async def chat(req: ChatRequest): ##` this function will be called when a POST request is made to the /chat endpoint, and it expects a JSON body that matches the ChatRequest model (i.e., it should have a "message" field of type string).`
    result = model.invoke(req.message) ## the `invoke` method of the `model` object is called with the user's message (req.message) as an argument. This method sends the message to the language model and returns the generated response, which is stored in the `result` variable.
    return {"reply": result.content}  ## the function returns a JSON response containing the generated reply from the language model. The response is structured as a dictionary with a single key "reply" that holds the content of the generated response (result.content).

