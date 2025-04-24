'''
🛠️ Requirements:
Python 3

pytesseract (Python wrapper for Tesseract)

Pillow (for image processing)

Tesseract-OCR installed on your system

🔧 Step 1: Install the dependencies
bash
Copy
Edit
pip install pytesseract pillow
You also need to install Tesseract-OCR itself:

Windows: Download from https://github.com/tesseract-ocr/tesseract

macOS: brew install tesseract

Ubuntu: sudo apt install tesseract-ocr

'''

from PIL import Image
import pytesseract

# Set this path only if Tesseract is not in your PATH environment variable
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def image_to_text(image_path):
    try:
        # Open the image
        img = Image.open(image_path)
        
        # Run OCR on the image
        text = pytesseract.image_to_string(img)
        
        return text.strip()
    except Exception as e:
        return f"Error: {e}"

# Example usage
if __name__ == "__main__":
    image_path = 'your_image.jpg'  # Replace with your image path
    extracted_text = image_to_text(image_path)
    print("Extracted Text:\n", extracted_text)
