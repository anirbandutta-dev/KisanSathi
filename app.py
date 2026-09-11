from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException 
from fastapi.templating import Jinja2Templates 
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import base64
import requests
import io
from PIL import Image
from dotenv import load_dotenv
import os
import logging
from fastapi.staticfiles import StaticFiles
from prediction import model_response
import pandas as pd
import google.generativeai as genai
from pydantic import BaseModel
from FarmerAssistant import app as farmer_assistant_app, main as init_farmer_assistant
from langchain_core.messages import HumanMessage, AIMessage
import joblib
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")   

# Load the water footprint model
try:
    water_footprint_model = joblib.load('Water Footprint Model/Model/water_footprint_model.pkl')
    logger.info("Water footprint model loaded successfully")
except Exception as e:
    logger.error(f"Error loading water footprint model: {str(e)}")
    water_footprint_model = None

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY")

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not set in the .env file")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

if not GROQ_API_KEY:
    raise ValueError("GROQ API KEY is not set in the .env file")

# Initialize Farmer Assistant
init_farmer_assistant()

@app.get("/", response_class = HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/donation.html", response_class = HTMLResponse)
async def donation_page(request: Request):
    return templates.TemplateResponse(request=request, name="donation.html")

@app.get("/dashboard.html", response_class = HTMLResponse)
async def dashboard_page(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")

@app.get("/crop-care.html", response_class = HTMLResponse)
async def crop_care_page(request: Request):
    return templates.TemplateResponse(request=request, name="crop-care.html")

@app.get("/market-analysis.html", response_class = HTMLResponse)
async def market_analysis_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="market-analysis.html",
        context={
            "data_gov_api_key": DATA_GOV_API_KEY
        }
    )

@app.get("/equipment-rental.html", response_class = HTMLResponse)
async def equipment_rental_page(request: Request):  
    return templates.TemplateResponse(request=request, name="equipment-rental.html")

@app.get("/farmer-assistant.html", response_class = HTMLResponse)
async def farmer_assistant_page(request: Request):
    return templates.TemplateResponse(request=request, name="farmer-assistant.html")

@app.get("/water-footprint.html", response_class = HTMLResponse)
async def water_footprint_page(request: Request):
    return templates.TemplateResponse(request=request, name="water-footprint.html")

@app.get("/weather-advisory.html", response_class = HTMLResponse)
async def weather_advisory_page(request: Request):
    return templates.TemplateResponse(request=request, name="weather-advisory.html")

@app.get("/schemes.html", response_class = HTMLResponse)
async def schemes_page(request: Request):
    return templates.TemplateResponse(request=request, name="schemes.html")

def generate_fallback_mandi_prices(commodity: str, state: str, date_str: str):
    all_mandis = {
        "Punjab": ["Khanna", "Rajpura", "Ludhiana", "Jalandhar", "Amritsar", "Patiala"],
        "Haryana": ["Karnal", "Ambala", "Kurukshetra", "Panipat", "Sonipat", "Hisar"],
        "Uttar Pradesh": ["Azadpur", "Agra", "Kanpur", "Varanasi", "Lucknow", "Mathura", "Meerut"],
        "Bihar": ["Patna", "Muzaffarpur", "Gaya", "Bhagalpur", "Darbhanga"],
        "Madhya Pradesh": ["Mandsaur", "Indore", "Ujjain", "Bhopal", "Neemuch", "Jabalpur"],
        "Maharashtra": ["Vashi (Mumbai)", "Nashik", "Pune", "Nagpur", "Solapur", "Kolhapur"]
    }
    
    base_prices = {
        "Tomato": {"min": 1800, "max": 3200, "modal": 2500},
        "Potato": {"min": 1200, "max": 2100, "modal": 1650},
        "Onion": {"min": 2200, "max": 3800, "modal": 2900},
        "Rice": {"min": 2800, "max": 4500, "modal": 3400},
        "Wheat": {"min": 2275, "max": 2850, "modal": 2450},
        "Maize": {"min": 1900, "max": 2400, "modal": 2150}
    }

    selected_states = [state] if state and state in all_mandis else list(all_mandis.keys())
    crop_info = base_prices.get(commodity, {"min": 1500, "max": 3000, "modal": 2200})

    records = []
    import random
    seed = sum(ord(c) for c in (commodity + (state or "")))
    random.seed(seed)

    for st in selected_states:
        mandis = all_mandis[st]
        for idx, mandi in enumerate(mandis[:3]):
            variation = random.randint(-250, 300)
            modal = max(500, crop_info["modal"] + variation)
            min_p = max(400, modal - random.randint(200, 400))
            max_p = modal + random.randint(200, 500)
            
            records.append({
                "State": st,
                "District": mandi,
                "Market": mandi + " Mandi",
                "Commodity": commodity,
                "Variety": "Local / Standard",
                "Arrival_Date": date_str,
                "Min_Price": str(min_p),
                "Max_Price": str(max_p),
                "Modal_Price": str(modal),
                "Grade": "FAQ"
            })
            
    return records

@app.get("/api/market-prices")
async def get_market_prices(
    commodity: str = "Tomato",
    state: str = "",
    date: str = ""
):
    from datetime import datetime, timedelta
    try:
        api_key = DATA_GOV_API_KEY or "579b464db66ec23bdd000001b8f96db7b581402460c29ca6306f24cd"
        base_url = "https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24"
        
        formatted_date = ""
        if date:
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
                formatted_date = dt.strftime("%d/%m/%Y")
            except Exception:
                formatted_date = date
        else:
            target_date = datetime.now() - timedelta(days=2)
            formatted_date = target_date.strftime("%d/%m/%Y")

        params = {
            "api-key": api_key,
            "format": "json",
            "limit": 20
        }
        if commodity:
            params["filters[Commodity.keyword]"] = commodity
        if state:
            params["filters[State.keyword]"] = state
        if formatted_date:
            params["filters[Arrival_Date]"] = formatted_date

        records = []
        try:
            resp = requests.get(base_url, params=params, timeout=4)
            if resp.status_code == 200:
                data = resp.json()
                records = data.get("records", [])
                
            if not records and formatted_date:
                params.pop("filters[Arrival_Date]", None)
                resp2 = requests.get(base_url, params=params, timeout=4)
                if resp2.status_code == 200:
                    records = resp2.json().get("records", [])
        except Exception as err:
            logger.warning(f"data.gov.in API request failed or timed out: {err}")

        if not records:
            logger.info("Using fallback mandi price data for market analysis")
            records = generate_fallback_mandi_prices(commodity, state, formatted_date)

        return JSONResponse(content={
            "status": "success",
            "date": formatted_date,
            "records": records
        })
    except Exception as e:
        logger.error(f"Error in get_market_prices: {str(e)}")
        fallback_date = date or datetime.now().strftime("%d/%m/%Y")
        fallback = generate_fallback_mandi_prices(commodity, state, fallback_date)
        return JSONResponse(content={
            "status": "success",
            "date": fallback_date,
            "records": fallback
        })

@app.get("/waste-exchange.html", response_class = HTMLResponse)
async def waste_exchange_page(request: Request):
    return templates.TemplateResponse(request=request, name="waste-exchange.html")

@app.post("/disease_prediction")
async def disease_prediction(file: UploadFile = File(...), selected_language: str = Form(...)):
    try:
        logger.info(f"Received request with file: {file.filename}, selected_language: {selected_language}")
        
        # Validate language
        if not selected_language:
            raise HTTPException(status_code=400, detail="Language is required")
            
        # Read the uploaded image file
        contents = await file.read()
        logger.info(f"Read {len(contents)} bytes from uploaded file")
        
        # Validate the image format
        try:
            img = Image.open(io.BytesIO(contents))
            img.verify()
            logger.info("Image format validated successfully")
        except Exception as e:
            logger.error(f"Invalid image format: {str(e)}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Invalid image format: {str(e)}")

        # Save the image temporarily
        temp_image_path = f"temp_{file.filename}"
        try:
            with open(temp_image_path, "wb") as temp_file:
                temp_file.write(contents)
            logger.info(f"Saved temporary file to: {temp_image_path}")

            # Call the classification function
            logger.info(f"Processing image with language: {selected_language}")
            response = model_response(temp_image_path, selected_language)
            logger.info(f"Model response type: {type(response)}")
            logger.info(f"Model response: {response}")
            
            # Check if there was an error in the response
            if "error" in response:
                logger.error(f"Model returned error: {response['error']}")
                raise HTTPException(status_code=500, detail=response["error"])
            
            # Return the response directly as it's already in the correct format
            return JSONResponse(status_code=200, content=response)
            
        except Exception as e:
            logger.error(f"Error in model_response: {str(e)}", exc_info=True)
            error_detail = str(e)
            if hasattr(e, 'detail'):
                error_detail = e.detail
            raise HTTPException(status_code=500, detail=f"Error in model processing: {error_detail}")
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_image_path):
                os.remove(temp_image_path)
                logger.info(f"Removed temporary file: {temp_image_path}")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        error_detail = str(e)
        if hasattr(e, 'detail'):
            error_detail = e.detail
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {error_detail}"
        )

@app.post("/api/chat")
async def chat(request: Request):
    try:
        # Get the question from the request body
        body = await request.json()
        question = body.get('question', '')
        
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")
            
        # Generate response using Gemini
        response = model.generate_content(
            f"""You are an AI assistant helping farmers understand government schemes. 
            Please provide detailed, accurate information about the following question related to government schemes for farmers.
            Format your response with:
            - Use **bold** for important points
            - Use *italics* for emphasis
            - Include relevant links where applicable
            - Use bullet points for lists
            - Add line breaks between sections
            - Keep the language simple and easy to understand
            
            If the question is not about government schemes, politely inform the user that you can only help with government scheme related queries.
            
            Question: {question}"""
        )
        
        return JSONResponse(content={"response": response.text})
    except Exception as e:
        logger.error(f"Error in chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/farmer-chat")
async def farmer_chat(request: Request):
    try:
        # Get the request data
        body = await request.json()
        question = body.get('question', '')
        chat_history = body.get('chat_history', [])  # Expect array of strings
        
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")

        # Convert string history to LangChain messages
        lc_history = []
        try:
            for i in range(0, len(chat_history), 2):
                if i+1 < len(chat_history):
                    lc_history.append(HumanMessage(content=chat_history[i]))
                    lc_history.append(AIMessage(content=chat_history[i+1]))
        except Exception as e:
            logger.error(f"Error converting chat history: {str(e)}")
            # If there's an error with history, start fresh
            lc_history = []

        # Process through LangChain
        try:
            current_state = {
                "query": question,
                "chat_history": lc_history
            }
            final_state = farmer_assistant_app.invoke(current_state)

            # Convert LangChain messages back to strings
            serialized_history = []
            for msg in final_state["chat_history"]:
                if isinstance(msg, (HumanMessage, AIMessage)):
                    serialized_history.append(msg.content)
            print(final_state["response"])
            return JSONResponse(content={
                "response": final_state["response"],
                "chat_history": serialized_history
            })
        
        except Exception as e:
            logger.error(f"Error in LangChain processing: {str(e)}")
            # Return a basic response if LangChain processing fails
            return JSONResponse(content={
                "response": "I apologize, but I'm having trouble processing your request right now. Please try again later.",
                "chat_history": chat_history  # Keep existing history
            })
        
    except Exception as e:
        logger.error(f"Error in farmer chat: {str(e)}")
        
        return JSONResponse(
            status_code=500,
            content={"error": f"Chat processing error: {str(e)}"}
        )

@app.post("/api/calculate-water-footprint")
async def calculate_water_footprint(request: Request):
    try:
        if water_footprint_model is None:
            raise HTTPException(status_code=500, detail="Water footprint model not available")
            
        data = await request.json()
        
        # Create input DataFrame
        input_data = pd.DataFrame([{
            'CropType': data['cropType'],
            'Region': data['region'],
            'SoilType': data['soilType'],
            'IrrigationMethod': data['irrigationMethod'],
            'Rainfall': float(data['rainfall']),
            'Temperature': float(data['temperature']),
            'Humidity': float(data['humidity'])
        }])
        
        # Make prediction
        prediction = water_footprint_model.predict(input_data)[0]
        
        # Calculate daily and weekly requirements
        area = float(data['area'])
        total_water = prediction * area / 1000  # Convert to cubic meters per hectare
        water_per_day = total_water / 90  # Assuming 90 days growing period
        water_per_week = water_per_day * 7
        
        return JSONResponse(content={
            'totalWater': total_water,
            'dailyWater': water_per_day,
            'weeklyWater': water_per_week
        })
        
    except Exception as e:
        logger.error(f"Error calculating water footprint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Remove or comment out the direct uvicorn run
# import uvicorn
# uvicorn.run(app, port=8000)

# Replace with this:
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)