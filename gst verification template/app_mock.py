"""
Mock GST Verification Service for Development/Testing
This service simulates the GST verification without connecting to the actual government portal
"""
from flask import Flask, jsonify, request
import uuid
import base64
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import random
import string

from asgiref.wsgi import WsgiToAsgi

app = Flask(__name__)
asgi_app = WsgiToAsgi(app)

# Store mock sessions
gstSessions = {}

# Mock GST database for testing
MOCK_GST_DATABASE = {
    "27AAPFU0939F1ZV": {
        "gstin": "27AAPFU0939F1ZV",
        "lgnm": "ABC PRIVATE LIMITED",
        "tradeNam": "ABC Traders",
        "sts": "Active",
        "dty": "Regular",
        "rgdt": "01/07/2017",
        "ctb": "Manufacturer",
        "pradr": {
            "addr": {
                "bnm": "Building 123",
                "st": "MG Road",
                "loc": "Pune",
                "dst": "Pune",
                "stcd": "Maharashtra",
                "pncd": "411001"
            }
        }
    },
    "29AABCT1332L1ZZ": {
        "gstin": "29AABCT1332L1ZZ",
        "lgnm": "XYZ CORPORATION",
        "tradeNam": "XYZ Corp",
        "sts": "Active",
        "dty": "Regular",
        "rgdt": "15/08/2017",
        "ctb": "Service Provider",
        "pradr": {
            "addr": {
                "bnm": "Tower A",
                "st": "Whitefield",
                "loc": "Bangalore",
                "dst": "Bangalore Urban",
                "stcd": "Karnataka",
                "pncd": "560066"
            }
        }
    }
}

def generate_captcha_image(text):
    """Generate a simple CAPTCHA image with the given text"""
    # Create image
    width, height = 200, 80
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # Add some noise lines
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        draw.line([(x1, y1), (x2, y2)], fill='lightgray', width=1)
    
    # Draw text
    try:
        # Try to use a default font, fallback to basic if not available
        font = ImageFont.truetype("arial.ttf", 36)
    except:
        font = ImageFont.load_default()
    
    # Calculate text position (centered)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (width - text_width) // 2
    y = (height - text_height) // 2
    
    # Draw the text
    draw.text((x, y), text, fill='black', font=font)
    
    # Add some noise dots
    for _ in range(100):
        x = random.randint(0, width)
        y = random.randint(0, height)
        draw.point((x, y), fill='gray')
    
    return image


@app.route("/api/v1/getCaptcha", methods=["GET"])
def getCaptcha():
    """Generate a mock CAPTCHA for testing"""
    try:
        # Generate random CAPTCHA text
        captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Generate CAPTCHA image
        captcha_image = generate_captcha_image(captcha_text)
        
        # Convert to base64
        buffered = BytesIO()
        captcha_image.save(buffered, format="PNG")
        captcha_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # Create session
        session_id = str(uuid.uuid4())
        gstSessions[session_id] = {
            "captcha_text": captcha_text,
            "created_at": None  # Could add timestamp if needed
        }
        
        print(f"Generated CAPTCHA: {captcha_text} for session: {session_id}")
        
        json_response = {
            "sessionId": session_id,
            "image": "data:image/png;base64," + captcha_base64,
        }
        
        return jsonify(json_response)
    
    except Exception as e:
        print(f"Error generating CAPTCHA: {e}")
        return jsonify({"error": "Error in fetching captcha"}), 500


@app.route("/api/v1/getGSTDetails", methods=["POST"])
def getGSTDetails():
    """Verify GSTIN with mock data"""
    try:
        session_id = request.json.get("sessionId")
        gstin = request.json.get("GSTIN")
        captcha = request.json.get("captcha")
        
        # Validate session
        if session_id not in gstSessions:
            return jsonify({"error": "Invalid or expired session"}), 400
        
        session_data = gstSessions[session_id]
        
        # Validate CAPTCHA (case-insensitive for easier testing)
        if captcha.upper() != session_data["captcha_text"].upper():
            return jsonify({"error": "Invalid CAPTCHA"}), 400
        
        # Clean up session after use
        del gstSessions[session_id]
        
        # Check if GSTIN exists in mock database
        if gstin in MOCK_GST_DATABASE:
            print(f"GSTIN {gstin} found in mock database")
            return jsonify(MOCK_GST_DATABASE[gstin])
        else:
            # Return a generic response for unknown GSTINs
            print(f"GSTIN {gstin} not found in mock database, returning generic response")
            return jsonify({
                "gstin": gstin,
                "lgnm": "MOCK COMPANY LIMITED",
                "tradeNam": "Mock Traders",
                "sts": "Active",
                "dty": "Regular",
                "rgdt": "01/01/2020",
                "ctb": "Manufacturer",
                "pradr": {
                    "addr": {
                        "bnm": "Mock Building",
                        "st": "Mock Street",
                        "loc": "Mock Location",
                        "dst": "Mock District",
                        "stcd": "Mock State",
                        "pncd": "000000"
                    }
                }
            })
    
    except Exception as e:
        print(f"Error in GST verification: {e}")
        return jsonify({"error": "Error in fetching GST Details"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "Mock GST Verification Service"})


if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("Mock GST Verification Service")
    print("=" * 60)
    print("This is a MOCK service for development/testing purposes")
    print("It does NOT connect to the actual government GST portal")
    print("=" * 60)
    print(f"Available mock GSTINs:")
    for gstin in MOCK_GST_DATABASE.keys():
        print(f"  - {gstin}")
    print("=" * 60)
    print("Starting server on http://0.0.0.0:5001")
    print("=" * 60)
    uvicorn.run(asgi_app, host='0.0.0.0', port=5001)
