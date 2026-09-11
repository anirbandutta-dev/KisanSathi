import os
import tensorflow as tf
import json
from PIL import Image
import numpy as np
import io
import logging
import base64
import requests
from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

working_dir = os.getcwd()

# print("Your working directory is: ", working_dir)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError("GROQ API KEY is not set in the .env file")
def load_resources():
    try:
        candidate_model_paths = [
            os.path.join(working_dir, "Disease prediction Model", "trained_model", "plant_disease_prediction.keras"),
            os.path.join(working_dir, "Disease prediction Model", "trained_model", "plant_disease_prediction1.keras"),
            os.path.join(working_dir, "Disease prediction Model", "trained_model", "plant_disease_prediction.h5"),
        ]
        
        model_path = None
        for path in candidate_model_paths:
            if os.path.exists(path):
                model_path = path
                break

        if not model_path:
            trained_model_dir = os.path.join(working_dir, "Disease prediction Model", "trained_model")
            if os.path.exists(trained_model_dir):
                for f in os.listdir(trained_model_dir):
                    if f.endswith(".keras") or f.endswith(".h5"):
                        model_path = os.path.join(trained_model_dir, f)
                        break

        class_indices_path = os.path.join(working_dir, "Disease prediction Model", "class_indices.json")

        logger.info(f"Loading model from: {model_path}")
        logger.info(f"Loading class indices from: {class_indices_path}")

        if not model_path or not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file not found in: {os.path.join(working_dir, 'Disease prediction Model', 'trained_model')}")
        if not os.path.exists(class_indices_path):
            raise FileNotFoundError(f"Class indices file not found at: {class_indices_path}")

        try:
            logger.info(f"Loading Keras model from {model_path}...")
            prediction_model = tf.keras.models.load_model(model_path, compile=False)
            logger.info("✅ Model loaded successfully from Keras file!")
        except Exception as e:
            logger.warning(f"Failed to load model file directly ({str(e)}). Creating Xception architecture fallback...")
            prediction_model = create_model_architecture()
            weights_path = os.path.join(working_dir, "Disease prediction Model", "model_weights.weights.h5")
            if os.path.exists(weights_path):
                logger.info("Loading weights into correct architecture...")
                prediction_model.load_weights(weights_path)
                logger.info("✅ Model created and weights loaded successfully!")
            else:
                logger.warning("No weights file found, using model with ImageNet weights only")

        if os.path.exists(class_indices_path):
            with open(class_indices_path, "r") as f:
                content = f.read()
                class_indices = json.loads(content)
                logger.info("Class indices loaded successfully from class_indices.json")
        else:
            raise FileNotFoundError(f"Class indices file not found at: {class_indices_path}")

        return prediction_model, class_indices
    except Exception as e:
        logger.error(f"Error loading resources: {str(e)}", exc_info=True)
        raise

def create_model_architecture():
    """Create the correct Xception-based model architecture"""
    from tensorflow.keras.applications import Xception
    from tensorflow.keras.layers import BatchNormalization
    
    base_model = Xception(
        weights='imagenet',
        include_top=False,
        input_shape=(224, 224, 3),
        pooling='avg'
    )
    
    model = tf.keras.Sequential([
        base_model,
        BatchNormalization(),
        tf.keras.layers.Dense(256, activation='relu'),
        tf.keras.layers.Dropout(0.5),
        tf.keras.layers.Dense(38, activation='softmax')
    ])
    
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.00001),
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    
    return model

prediction_model, class_indices = load_resources()

LANGUAGES = {
    "English": "en", # English 
    "हिन्दी": "hi", # Hindi 
    "ਪੰਜਾਬੀ": "pa", # Punjabi 
    "ಕನ್ನಡ": "kn" # Kannada
}
def load_and_preprocess_image(image):
    img = Image.open(image).convert('RGB').resize((224, 224))
    return np.expand_dims(np.array(img)/255.0, axis=0)

def predict_disease(image):
    processed_image = load_and_preprocess_image(image)
    predictions = prediction_model.predict(processed_image)
    predicted_class = class_indices[str(np.argmax(predictions))]
    return predicted_class

def model_response(image_path: str, selected_language: str) -> dict:
    try:
        logger.info(f"Processing image: {image_path}")
        logger.info(f"Selected language: {selected_language}")

        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")

        disease = predict_disease(image_path)
        logger.info(f"Predicted disease: {disease}")

        if not disease:
            raise ValueError("Could not classify disease from the given input image.")
        
        if selected_language not in LANGUAGES:
            raise ValueError(f"Unsupported language: {selected_language}")
        
        lang_code = LANGUAGES[selected_language]
        logger.info(f"Using language code: {lang_code}")

        # Read and encode the image
        with open(image_path, "rb") as image_file:
            image_content = image_file.read()
            encoded_image = base64.b64encode(image_content).decode("utf-8")
            logger.info("Image encoded successfully")

        # Validate the image format
        try:
            img = Image.open(io.BytesIO(image_content))
            img.verify()
            logger.info("Image format validated successfully")
        except Exception as e:
            logger.error(f"Invalid image format: {str(e)}", exc_info=True)
            return {"error": f"Invalid image format: {str(e)}"}
        
        query = (
            f"Given the crop disease: {disease}, please provide a detailed explanation of its causes, "
            f"prevention methods, and treatment options. Respond in the following language: {selected_language}.\n\n"
            "CRITICAL FORMATTING RULES:\n"
            "1. Use '### ' for main section headings (e.g. Causes, Prevention, Treatment).\n"
            "2. Leave a DOUBLE BLANK LINE before and after every heading, paragraph, and list.\n"
            "3. Use bullet points ('- ') for lists. Bold important terms.\n"
            "4. Organize your response into short, easy-to-read paragraphs. Do NOT output a single wall of text.\n"
        )
        logger.info(f"Generated query: {query}")

        # Format the message according to GROQ API requirements
        messages = [
            {
                "role": "user",
                "content": query
            }
        ]

        # API Request
        logger.info("Sending request to GROQ API")
        response = requests.post(
            GROQ_API_URL,
            json={
                "model": "openai/gpt-oss-20b",
                "messages": messages
            },
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            logger.info("Successfully received response from GROQ API")
            return result
        else:
            error_msg = f"API Error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            return {
                "choices": [
                    {
                        "message": {
                            "content": f"### 🍃 Predicted Disease: **{disease}**\n\n⚠️ **Notice:** Detailed LLM recommendation could not be retrieved from Groq API (`Error {response.status_code}`). Please ensure your `GROQ_API_KEY` in `.env` is a valid Groq API key (starts with `gsk_`).\n\n**Standard Guidance for {disease}:**\n- **Sanitation:** Remove and safely dispose of affected leaves/plants.\n- **Watering:** Water at the base of the plant to keep foliage dry.\n- **Treatment:** Consult local agricultural advisory or apply fungicide appropriate for **{disease}**."
                        }
                    }
                ]
            }
        
    except FileNotFoundError as e:
        error_msg = f"Image file not found: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"choices": [{"message": {"content": f"⚠️ **Error:** {error_msg}"}}]}
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON response: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"choices": [{"message": {"content": f"⚠️ **Error:** {error_msg}"}}]}
    except requests.exceptions.RequestException as e:
        error_msg = f"API request failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"choices": [{"message": {"content": f"⚠️ **Error:** {error_msg}"}}]}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"choices": [{"message": {"content": f"⚠️ **Error:** {error_msg}"}}]}
    
if __name__ == "__main__":
    from fastapi.responses import HTMLResponse, JSONResponse 
    image_path = "C:/Users/LAKSHYA PALIWAL/Downloads/Deploy using streamlit/Crop Disease Deteciton/0b943ada-01a9-4ce0-a607-e799394856de___Crnl_L.Mold 7008.JPG"
      # Replace with actual uploaded image path
    additional_info = "The dog seems to be limping and has a small wound on its leg."
    result = model_response(image_path, selected_language="English")
    # result = response.json()
    print(result["choices"][0]["message"]["content"])