import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import json
import time
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
text_model = genai.GenerativeModel('gemini-1.5-pro-latest')
vision_model = genai.GenerativeModel('gemini-1.5-pro-latest')

# Configure the app
st.set_page_config(
    page_title="Vaccination Reminder Chatbot",
    page_icon="💉",
    layout="wide"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "vaccination_data" not in st.session_state:
    st.session_state.vaccination_data = None
if "vaccination_card_processed" not in st.session_state:
    st.session_state.vaccination_card_processed = False
if "last_uploaded_file" not in st.session_state:
    st.session_state.last_uploaded_file = None

def extract_vaccination_data(image_bytes):
    """Extract vaccination details from card image"""
    prompt = """
    You are a medical document specialist analyzing a vaccination card. Extract ALL details including:
    1. PATIENT INFORMATION:
       - Full name (exact spelling)
       - Date of birth (YYYY-MM-DD format)
       - Patient ID/Health number if present
    
    2. VACCINATION HISTORY:
       - For EACH vaccine entry:
         * Vaccine name (official name)
         * Date administered (YYYY-MM-DD)
    
    3. UPCOMING VACCINES:
       - Any mentioned future vaccines
       - Recommended due dates
    
    Return STRICT JSON format (don't include any other text) with this structure:
    {
        "patient_info": {
            "name": "",
            "dob": "",
            "patient_id": ""
        },
        "vaccines_received": [
            {
                "name": "",
                "date": ""
            }
        ],
        "due_vaccines": [
            {
                "name": "",
                "due_date": ""
            }
        ]
    }
    """
    
    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = vision_model.generate_content(
            [prompt, image],
            generation_config={"response_mime_type": "application/json"}
        )
        
        response_text = response.text
        if response_text.startswith('```json'):
            response_text = response_text[7:-3]
        
        return json.loads(response_text)
    except Exception as e:
        st.error(f"Error processing card: {str(e)}")
        return None

def get_vaccine_precautions(vaccine_name):
    """Get 2-3 precautions for a specific vaccine"""
    prompt = f"""
    Provide exactly 2-3 important precautions for someone about to receive a {vaccine_name} vaccine.
    Return as a JSON array only:
    {{
        "precautions": []
    }}
    """
    
    try:
        response = text_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        response_text = response.text
        if response_text.startswith('```json'):
            response_text = response_text[7:-3]
        return json.loads(response_text)["precautions"]
    except:
        return [
            "Consult your doctor before vaccination",
            "Inform about any allergies"
        ]

def process_uploaded_file(uploaded_file):
    """Process uploaded vaccination card file"""
    try:
        # Reset previous state for new upload
        st.session_state.vaccination_card_processed = False
        st.session_state.vaccination_data = None
        
        file_bytes = uploaded_file.getvalue()
        
        if uploaded_file.type not in ["image/jpeg", "image/png"]:
            return {"error": "Only JPEG/PNG images are supported"}
        
        st.image(file_bytes, caption="Uploaded Vaccination Card", use_column_width=True)
        
        with st.spinner("Analyzing vaccination card..."):
            vaccine_data = extract_vaccination_data(file_bytes)
            if vaccine_data:
                # Add precautions for due vaccines
                if "due_vaccines" in vaccine_data:
                    for vaccine in vaccine_data["due_vaccines"]:
                        vaccine["precautions"] = get_vaccine_precautions(vaccine["name"])
                
                st.session_state.vaccination_data = vaccine_data
                st.session_state.vaccination_card_processed = True
                st.session_state.last_uploaded_file = uploaded_file.name
                return {"success": True, "data": vaccine_data}
            else:
                return {"error": "Failed to extract vaccination data"}
                
    except Exception as e:
        return {"error": f"File processing error: {str(e)}"}

# UI Components
def render_sidebar():
    with st.sidebar:
        st.header("📄 Upload Vaccination Card")
        uploaded_file = st.file_uploader(
            "Choose your vaccination card image (JPEG/PNG)",
            type=["jpg", "jpeg", "png"],
            key="vaccine_card_uploader"
        )
        
        if uploaded_file is not None:
            # Check if this is a new file
            if (st.session_state.last_uploaded_file != uploaded_file.name or 
                not st.session_state.vaccination_card_processed):
                
                result = process_uploaded_file(uploaded_file)
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success("Vaccination card processed successfully!")
                    st.balloons()

def render_chat_interface():
    st.title("💉 Vaccination Specialist Chatbot")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input("Ask about your vaccinations..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            if not st.session_state.vaccination_card_processed:
                st.warning("Please upload your vaccination card first")
            else:
                response = text_model.generate_content(
                    f"Based on this vaccination data: {json.dumps(st.session_state.vaccination_data, indent=2)}\n\n"
                    f"Answer this question: {prompt}\n\n"
                    "Be concise and factual. Current date is {time.strftime('%Y-%m-%d')}"
                )
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})

def render_vaccination_details():
    if st.session_state.vaccination_card_processed:
        st.subheader("📋 Your Vaccination Details")
        data = st.session_state.vaccination_data
        
        with st.expander("👤 Patient Information"):
            if "patient_info" in data:
                st.write(f"**Name:** {data['patient_info'].get('name', 'N/A')}")
                st.write(f"**Date of Birth:** {data['patient_info'].get('dob', 'N/A')}")
                st.write(f"**Patient ID:** {data['patient_info'].get('patient_id', 'N/A')}")
        
        with st.expander("💉 Vaccines Received"):
            if "vaccines_received" in data and data["vaccines_received"]:
                for vax in data["vaccines_received"]:
                    st.write(f"**{vax.get('name', 'Vaccine')}**")
                    st.write(f"- Date: {vax.get('date', 'N/A')}")
                    st.write("---")
            else:
                st.write("No vaccination history found")
        
        with st.expander("⚠️ Due Vaccines & Precautions"):
            if "due_vaccines" in data and data["due_vaccines"]:
                for vax in data["due_vaccines"]:
                    st.write(f"**{vax.get('name', 'Vaccine')}**")
                    st.write(f"- Due Date: {vax.get('due_date', 'N/A')}")
                    
                    if "precautions" in vax:
                        st.write("- Precautions:")
                        for precaution in vax["precautions"]:
                            st.write(f"  • {precaution}")
                    
                    st.write("---")
            else:
                st.write("No upcoming vaccines found")

# Main App Flow
render_sidebar()
render_chat_interface()
render_vaccination_details()