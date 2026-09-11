
## 🚀 Installation & Setup

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Git

### Step 1: Clone the Repository
```bash
git clone https://github.com/21lakshh/Kisaan-Sathi.git   
cd Kisaan-Sathi
```

### Step 2: Create Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt ##THESE ARE NOT YET ADDED
```

### Step 4: Environment Configuration
Create a `.env` file in the root directory:
```bash
GROQ_API_KEY=your_groq_key_here
DATA_GOV_API_KEY=your_data_gov_key_here
GEMINI_API_KEY=your_gemini_key_here
OPEN_WEATHER_API_KEY=your_weather_api_key_here
```

### Step 5: Run the Application
```bash
python app.py
```

The application will be available at `http://127.0.0.1:8000`
