import os
import logging
from dotenv import load_dotenv
import eventlet
eventlet.monkey_patch()  # Required for SocketIO with eventlet

from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from pyngrok import ngrok
import lt_app.config as config
from lt_app.transcriber import WhisperTranscriber
from lt_app.audio import decode_webm_chunk

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask and SocketIO
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet', cors_allowed_origins="*")

# Initialize Whisper (singleton)
transcriber = WhisperTranscriber.get_instance()

# Start ngrok tunnel
ngrok_token = os.getenv('NGROK_AUTH_TOKEN')
if not ngrok_token:
    logger.warning("⚠️ NGROK_AUTH_TOKEN not found in .env file")
else:
    try:
        ngrok.set_auth_token(ngrok_token)
        public_url = ngrok.connect(5000).public_url
        logger.info(f"🌍 Ngrok tunnel started: {public_url}")
    except Exception as e:
        logger.error(f"❌ Failed to start ngrok tunnel: {e}")

@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connections."""
    logger.info(f"🔌 Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnections."""
    logger.info(f"🔌 Client disconnected: {request.sid}")

@socketio.on('audio_chunk')
async def handle_audio_chunk(data):
    """Handle incoming audio chunks from the browser."""
    try:
        # Decode WebM chunk to PCM
        audio_array, sample_rate = decode_webm_chunk(data['audio'])
        
        # Process with Whisper and emit results
        await transcriber.process_chunk(audio_array, socketio, request.sid)
        
    except Exception as e:
        logger.error(f"❌ Error processing audio chunk: {e}")
        await socketio.emit('transcription_error', 
                          {'error': 'Failed to process audio'}, 
                          room=request.sid)

if __name__ == '__main__':
    # Run the server
    try:
        logger.info("🚀 Starting server on port 5000...")
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        logger.error(f"❌ Failed to start server: {e}") 