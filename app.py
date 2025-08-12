import os
import tempfile
from flask import Flask, request, jsonify, render_template
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from PyPDF2 import PdfReader
import docx
import requests
from groq import Groq

# Try to import PyMuPDF as fallback
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# ------------------------
# Flask Setup
# ------------------------
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = tempfile.gettempdir()
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB limit

# ------------------------
# API Key & Client Setup
# ------------------------
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY not set in environment variables!")

client = Groq(api_key=GROQ_API_KEY)

# ------------------------
# Helper Functions
# ------------------------
def extract_text_from_pdf(file_path):
    text = ""
    
    # Try PyMuPDF first (more robust)
    if PYMUPDF_AVAILABLE:
        try:
            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text += page.get_text()
                # Limit to prevent excessive processing
                if len(text) > 10000:
                    break
            doc.close()
            return text.strip()
        except Exception as e:
            print(f"PyMuPDF extraction failed: {e}, trying PyPDF2...")
    
    # Fallback to PyPDF2
    try:
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            # Add timeout protection and better error handling
            for i, page in enumerate(reader.pages):
                try:
                    page_text = page.extract_text() or ""
                    text += page_text
                    # Limit to prevent excessive processing
                    if len(text) > 10000:  # Limit to 10k characters
                        break
                except Exception as page_error:
                    print(f"Warning: Failed to extract text from page {i}: {page_error}")
                    continue
    except Exception as e:
        raise RuntimeError(f"PDF extraction failed with both PyMuPDF and PyPDF2: {e}")
    return text.strip()

def extract_text_from_docx(file_path):
    text = ""
    try:
        doc = docx.Document(file_path)
        for para in doc.paragraphs:
            text += para.text + "\n"
    except Exception as e:
        raise RuntimeError(f"Word extraction failed: {e}")
    return text.strip()

def fetch_article_text(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text.strip()
    except Exception as e:
        raise RuntimeError(f"Article fetch failed: {e}")

def ask_groq(question, context):
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"GROQ API call failed: {e}")

def summarize_text(text):
    try:
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": "You are a helpful summarizer."},
                {"role": "user", "content": f"Summarize the following text:\n{text}"}
            ],
            temperature=0.3,
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"Summarization failed: {e}")

# ------------------------
# Routes
# ------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        file = request.files.get("file")
        question = request.form.get("question", "").strip()
        url = request.form.get("url", "").strip()

        if not question and not url:
            return jsonify({"error": "Please provide a question or an article URL."}), 400

        if url:
            text = fetch_article_text(url)
            answer = summarize_text(text) if not question else ask_groq(question, text)
            return jsonify({"answer": answer})

        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)

            if filename.lower().endswith(".pdf"):
                text = extract_text_from_pdf(file_path)
            elif filename.lower().endswith(".docx"):
                text = extract_text_from_docx(file_path)
            else:
                return jsonify({"error": "Only PDF and DOCX files are supported."}), 400

            answer = ask_groq(question, text)
            return jsonify({"answer": answer})

        return jsonify({"error": "No file or URL provided."}), 400

    except Exception as e:
        # Log the error for debugging
        print(f"ERROR in /ask route: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": "An error occurred while processing your request. Please try again."}), 500
    
@app.route("/qa", methods=["POST"])
def qa():
    try:
        data = request.get_json() or {}
        question = data.get("question", "").strip()
        context = data.get("context", "").strip()

        if not question or not context:
            return jsonify({"error": "Both 'question' and 'context' are required"}), 400

        answer = ask_groq(question, context)
        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/summarize", methods=["POST"])
def summarize():
    try:
        data = request.get_json() or {}
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"error": "'text' is required"}), 400

        summary = summarize_text(text)
        return jsonify({"summary": summary})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Run App
if __name__ == "__main__":
    app.run(debug=True)
