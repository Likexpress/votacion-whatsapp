from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

@app.route('/whatsapp', methods=['POST'])
def whatsapp_reply():
    incoming_msg = request.values.get('Body', '').lower()
    sender = request.values.get('From', '')

    # Aquí puedes generar un link único para el votante
    link_votacion = f"https://tuvotoseguro.com/votar?numero={sender}"

    # Responder al ciudadano
    response = MessagingResponse()
    msg = response.message()
    msg.body(f"Hola 👋 Gracias por comunicarte con el Sistema de Votación Ciudadana.\n\nPara emitir tu voto, haz clic en el siguiente enlace:\n👉 {link_votacion}\n\nEste enlace es único y válido por una sola vez.")
    
    return str(response)

if __name__ == '__main__':
    app.run(debug=True)
