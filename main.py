from flask import Flask, render_template, request, redirect, session, url_for ,jsonify
from flask_cors import CORS
import openai
import os
import re
from dotenv import load_dotenv
import subprocess
from flask_session import Session
import sqlite3
import bcrypt
from werkzeug.utils import secure_filename
from pyngrok import ngrok

from flask import send_from_directory

app = Flask(__name__)
# Temporarily allow any origin:
CORS(app, supports_credentials=True)


os.environ["OPENAI_API_KEY"] = "api key

openai.api_type = "azure"
openai.api_base = "https://majdi-m9o9rl7t-eastus2.cognitiveservices.azure.com"
openai.api_version = "2025-03-01-preview"
openai.api_key = api key


app.secret_key = 'geheime-sleutel'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
Session(app)

# ➔ Standaardroute = loginpagina
@app.route('/')
def index():
    return redirect('/index')

# Database setup
def init_db():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                password TEXT NOT NULL,
                profile_picture TEXT,
                subscription TEXT,
                payment_method TEXT
            )
        ''')
        conn.commit()

@app.route('/register', methods=['POST', 'OPTIONS'])
def register():
    origin = request.headers.get("Origin")
    allowed_origins = ["https://consultium.app"]

    # 👉 CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({"message": "CORS preflight OK"})
        if origin in allowed_origins:
            response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

    try:
        name     = request.form['name']
        email    = request.form['email']
        phone    = request.form['phone']
        password = request.form['password']
        subscription = request.form['subscription']
        payment_method = request.form['payment_method']

        # Wachtwoord hashen
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Profielfoto opslaan
        profile_picture = request.files.get('profile_picture')
        if profile_picture and profile_picture.filename != '':
            filename = secure_filename(profile_picture.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            profile_picture.save(filepath)
            profile_picture_url = f'uploads/{filename}'
        else:
            profile_picture_url = 'uploads/default.png'

        # ➕ Voeg gebruiker toe aan DB
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (name, email, phone, password, profile_picture, subscription, payment_method)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (name, email, phone, hashed_password, profile_picture_url, subscription, payment_method))
            conn.commit()

        response = jsonify({"success": True})
        if origin in allowed_origins:
            response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

    except sqlite3.IntegrityError:
        response = jsonify({"error": "❌ Dit e-mailadres is al geregistreerd!"})
        if origin in allowed_origins:
            response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response, 400

    except Exception as e:
        response = jsonify({"error": f"❌ Serverfout: {str(e)}"})
        if origin in allowed_origins:
            response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response, 500


@app.route('/api/login', methods=['POST', 'OPTIONS'])
def api_login():
    origin = request.headers.get("Origin")
    allowed_origins = ["https://consultium.app"]

    if request.method == 'OPTIONS':
        response = jsonify({"message": "CORS preflight OK"})
        if origin in allowed_origins:
            response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Headers", "Content-Type")
        response.headers.add("Access-Control-Allow-Methods", "POST, OPTIONS")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

    try:
        # 🚨 forceer JSON parsing
        data = request.get_json(force=True)

        if not data:
            raise ValueError("❌ Geen data ontvangen")

        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            raise ValueError("❌ Email of wachtwoord ontbreekt")

        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, password FROM users WHERE email = ?', (email,))
            user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[1]):
           response = jsonify({"success": True})
        else:
         response = jsonify({"error": "❌ Foute login"})
        return response, 401


        if origin in allowed_origins:
            response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

    except Exception as e:
        print(f"❌ Serverfout in login: {str(e)}")
        response = jsonify({"error": f"Serverfout: {str(e)}"})
        if origin in allowed_origins:
            response.headers.add("Access-Control-Allow-Origin", origin)
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response, 500


@app.route('/index', methods=['GET'])
def index_view():
    return jsonify({"status": "frontend hosted separately"}), 200



@app.route('/home')
def home():
    if 'user_id' not in session:
        return redirect('/index')
    return render_template('home.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/index')
# 🔹 Laad de API-key uit het .env-bestand
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

if api_key:
    print("✅ API Key geladen!")
else:
    print("❌ API Key NIET gevonden!")

# 🔹 Maak een OpenAI-client aan
client = openai.OpenAI(api_key=api_key)

def extract_section(text, section):
    """
    Zoek een sectie (S, O, E of P) in de GPT-output en pak alle regels
    tot aan de volgende sectiekop of het einde van de tekst.
    """
    # Regex zoekt naar bijvoorbeeld:
    # "S" aan het begin van een regel, gevolgd door alles tot de volgende
    # kop (S, O, E of P) of het einde (\Z).
    pattern = rf"^{section}\s*(.*?)(?=^[SOEP]\s|\Z)"
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)

    if match:
        extracted_text = match.group(1).strip()
        return extracted_text if extracted_text else "⚠️ Geen gegevens beschikbaar"

    return "⚠️ Sectie niet gevonden in de GPT-output"


def transcribe_audio(audio_path):
    if not os.path.exists(audio_path):
        return {"error": "❌ Audiobestand niet gevonden!"}

    print(f"🎧 Audio wordt getranscribeerd via Azure Whisper: {audio_path}")

    try:
        with open(audio_path, "rb") as f:
           response = client.audio.transcriptions.create(
     model="gpt-4o-transcribe",
    file=f,
    language="nl"
)

        raw_transcription = response.text
        print("📝 Ruwe transcriptie van Azure Whisper:", raw_transcription)

        # 🎯 Laat GPT-4o de transcriptie verbeteren met interpunctie en medische correcties
        system_message = """
       Je bent een geavanceerde medische AI-assistent die transcripties van huisartsconsulten **corrigeert en optimaliseert op basis van context en realisme**.

    ✅ **Wat moet je doen?**
    - **Corrigeer verkeerd herkende woorden op basis van de context.**
    - Voorbeeld: "airport" → "elleboog" als de context medisch relevant is.
    - Voorbeeld: "mijn knie is verstuikt" → "mijn enkel is verstuikt" als de rest van het gesprek over de enkel gaat.
    - **Behoud ALLE originele informatie** en verander niets aan de inhoud.
    - **Zorg voor grammaticaal correcte en natuurlijke zinnen**, zonder de betekenis aan te passen.
    - **Voeg correcte interpunctie toe** (punten, komma’s, hoofdletters) om de leesbaarheid te verbeteren.
    - **Laat de natuurlijke dialoogstructuur intact.**

    🚨 **Wat mag je NIET doen?**
    ❌ **Geen inkortingen** → Alle zinnen blijven behouden zoals in de originele transcriptie.
    ❌ **Geen informatie verwijderen of samenvatten**.
    ❌ **Geen interpretatie van de medische inhoud** → Je corrigeert alleen fouten en maakt de tekst natuurlijker.
    ❌ **Geen toevoegingen van eigen interpretaties of extra informatie**.

    💡 **Voorbeelden van correcties die WEL mogen:**
    **Input:**
    "Ik heb pijn in mijn airport en het doet pijn bij beweging."
    **Output:**
    "Ik heb pijn in mijn elleboog en het doet pijn bij beweging."

    **Input:**
    "Ik ben gevallen en heb mijn enkel bezeerd. Mijn knie is verstuikt."
    **Output:**
    "Ik ben gevallen en heb mijn enkel bezeerd. Mijn enkel is verstuikt."

    **Input:**
    "Dokter: Waar heeft u pijn Patiënt: Ja het doet pijn hier en eh ja ook een beetje in mijn nek maar vooral hier."
    **Output:**
    "Dokter: Waar heeft u pijn? Patiënt: Ja, het doet pijn hier en eh, ja, ook een beetje in mijn nek, maar vooral hier."

    **Verbeter de volgende transcriptie op deze manier, zonder inkorting of wijziging van de inhoud:**
    """

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=5000,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": raw_transcription}
            ]
        )

        improved_transcription = response.choices[0].message.content.strip()
        print("✅ Verbeterde transcriptie:", improved_transcription)

        return {"transcription": improved_transcription}

    except Exception as e:
        print(f"❌ Azure Whisper fout: {str(e)}")
        return {"error": f"Azure Whisper fout: {str(e)}"}


def chat_with_gpt(prompt):
    """🎯 Verwerkt de tekst met ChatGPT om een SOEP-verslag te genereren."""
    if not prompt or prompt.strip() == "":
        return {"error": "Geen bruikbare tekst gevonden in de input."}

    system_message = """
Je bent een medische AI-assistent die medische vrije tekstnotities omzet in een gestructureerd SOEP-verslag. Volg de volgende richtlijnen: \n\n1. **S (Subjectief)**: Alles wat de patiënt vertelt zonder objectieve verificatie. Voorbeelden: klachten, pijnscore, levensstijl, zorgen. **Let op**: geen vitale functies, medicatie, of labuitslagen. \n\n2. **O (Objectief)**: Verifieerbare feiten zoals vitale functies, lichamelijk onderzoek, labuitslagen, medicatie. **Let op**: geen subjectieve elementen. \n\n3. **E (Evaluatie)**: Werkdiagnose(s), differentiële diagnoses, beoordeling van ernst. **Let op**: geen nieuwe feiten, alleen interpretatie. \n\n4. **P (Plan)**: Beleid zoals aanvullend onderzoek, behandeling, medicatie-aanpassing, verwijzing, follow-up. **Let op**: geen S/O/E informatie. \n\nGebruik de volgorde: S, O, E, P. Vermijd fouten zoals: vaccins en medicatie in S zetten, of het verwarren van subjectieve klachten met objectieve gegevens. Het doel is een helder, gestructureerd verslag zonder verwarring of dubbele vermeldingen. maak nu een soepverslag van het volgende consult:
"""
    try:
        response = client.chat.completions.create(
            model="ft:gpt-4o-2024-08-06:personal::BP57I80W",
            max_tokens=1500,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ]
        )

        output = response.choices[0].message.content.strip()

        # ✅ Debugging: Print de volledige GPT-output in de terminal
        print("🔍 GPT Output:\n", output)

        # ✅ Zorg ervoor dat we altijd iets tonen als de regex faalt
        return {
            "s": extract_section(output, "S") or output,
            "o": extract_section(output, "O") or output,
            "e": extract_section(output, "E") or output,
            "p": extract_section(output, "P") or output
        }

    except Exception as e:
        return {"error": f"GPT Fout: {str(e)}"}

@app.route("/generate-soep", methods=["POST"])
def generate_soep():
    """📜 Ontvangt tekst en genereert een SOEP-verslag via ChatGPT."""
    try:
        data = request.get_json()
        if not data or "prompt" not in data:
            return jsonify({"error": "Ongeldige JSON of ontbrekende 'prompt'"}), 400

        prompt = data["prompt"]
        result = chat_with_gpt(prompt=prompt)

        return jsonify(result)

    except Exception as e:
        print(f"❌ Serverfout: {e}")
        return jsonify({"error": f"Serverfout: {str(e)}"}), 500

@app.route("/transcribe-audio", methods=["POST"])
def transcribe_audio_endpoint():
    try:
        if "file" not in request.files:
            return jsonify({"error": "Geen audiobestand ontvangen!"}), 400

        file = request.files["file"]
        input_path = "temp_audio.webm"
        output_path = "temp_audio.mp3"

        # Sla originele webm op
        file.save(input_path)

        # Converteer met ffmpeg naar mp3
        subprocess.run(["ffmpeg", "-y", "-i", input_path, output_path], check=True)

        # Transcribe mp3
        result = transcribe_audio(output_path)

        # Opruimen
        os.remove(input_path)
        os.remove(output_path)

        return jsonify(result)

    except Exception as e:
        print(f"❌ Fout bij transcriptie: {str(e)}")
        return jsonify({"error": f"Serverfout: {str(e)}"}), 500


@app.route("/chat-assistant", methods=["POST", "OPTIONS"])
def chat_assistant():
    if request.method == "OPTIONS":
        # Optioneel kun je hier handmatig de juiste headers instellen
        return jsonify({"ok": True}), 200
    """
    Ontvangt een bericht van de huisarts en geeft een antwoord van de AI-assistent.
    """
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "Ongeldige JSON of ontbrekende 'message'"}), 400

        user_message = data["message"]

        # Preprompt voor de AI-assistent gericht op algemene huisartsen vragen
        preprompt = """
        Je bent een ervaren medische assistent die huisartsen ondersteunt bij algemene vragen.
        Beantwoord vragen over medicijnen, interacties, doseringen, bijwerkingen en algemene medische kennis op een duidelijke en beknopte manier.
        Als dat nodig is, verwijs naar betrouwbare bronnen. Geef altijd nauwkeurige en contextuele informatie.
        """

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=500,
            messages=[
                {"role": "system", "content": preprompt},
                {"role": "user", "content": user_message}
            ]
        )

        assistant_reply = response.choices[0].message.content.strip()
        return jsonify({"reply": assistant_reply})
    except Exception as e:
        print(f"❌ Chat-assistent fout: {str(e)}")
        return jsonify({"error": f"Serverfout: {str(e)}"}), 500


if __name__ == "__main__":
    print("🚀 Flask server wordt gestart...")

    # # 🌍 Start ngrok-tunnel en toon link
    public_url = ngrok.connect(5000)
    print("🌍 Jouw endpoint:", public_url)

    # Start de Flask-server
    init_db()

    app.run()
