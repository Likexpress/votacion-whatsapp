from flask import Flask, request, render_template_string, redirect, url_for
from twilio.twiml.messaging_response import MessagingResponse

app = Flask(__name__)

# Datos temporales en memoria (luego usaremos base de datos)
votos_registrados = {}

# Página principal de votación
@app.route('/votar')
def votar():
    numero = request.args.get('numero')
    if not numero:
        return "Acceso no válido"

    if numero in votos_registrados:
        return "Este número ya ha votado. Gracias por participar."

    html = '''
    <h2>Elecciones Ciudadanas 2025</h2>
    <form method="post" action="/enviar_voto">
        <input type="hidden" name="numero" value="{{ numero }}">
        <label>Elige tu candidato:</label><br>
        <input type="radio" name="candidato" value="Candidato A" required> Candidato A<br>
        <input type="radio" name="candidato" value="Candidato B"> Candidato B<br>
        <input type="radio" name="candidato" value="Candidato C"> Candidato C<br><br>
        <button type="submit">Votar</button>
    </form>
    '''
    return render_template_string(html, numero=numero)

# Ruta para recibir el voto
@app.route('/enviar_voto', methods=['POST'])
def enviar_voto():
    numero = request.form.get('numero')
    candidato = request.form.get('candidato')

    if numero in votos_registrados:
        return "Ya registramos tu voto."

    votos_registrados[numero] = candidato
    return f"Gracias por tu voto. Has elegido: {candidato}"

# WhatsApp responde con un link
@app.route('/whatsapp', methods=['POST'])
def whatsapp_reply():
    sender = request.values.get('From', '')

    link_votacion = f"https://votacion-whatsapp.onrender.com/votar?numero={sender}"


    response = MessagingResponse()
    msg = response.message()
    msg.body(f"Hola, gracias por participar en la votación.\n\nHaz clic para votar:\n{link_votacion}")
    return str(response)

if __name__ == '__main__':
    app.run(debug=True)
