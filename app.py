from flask import Flask, request, render_template_string
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime

app = Flask(__name__)

# ---------------------------
# Almacén temporal de votos (diccionario en memoria)
# ---------------------------
votos_registrados = {}

# ---------------------------
# Ruta: Página de votación
# ---------------------------
@app.route('/votar')
def votar():
    numero = request.args.get('numero')
    
    if not numero:
        return "Acceso no válido"

    if numero in votos_registrados:
        return "Este número ya ha votado. Gracias por participar."

    # HTML del formulario con Bootstrap y selección dinámica de país y ciudad
    html = '''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Elecciones Ciudadanas 2025</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <script>
            async function cargarPaises() {
                const res = await fetch("https://countriesnow.space/api/v0.1/countries");
                const data = await res.json();
                const paises = data.data;

                const selectPais = document.getElementById("pais");
                paises.forEach(p => {
                    const option = document.createElement("option");
                    option.value = p.country;
                    option.textContent = p.country;
                    selectPais.appendChild(option);
                });

                selectPais.addEventListener("change", () => {
                    const paisSeleccionado = selectPais.value;
                    cargarCiudades(paisSeleccionado);
                });
            }

            async function cargarCiudades(pais) {
                const res = await fetch("https://countriesnow.space/api/v0.1/countries/cities", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ country: pais })
                });

                const data = await res.json();
                const ciudades = data.data;
                const selectCiudad = document.getElementById("ciudad");

                selectCiudad.innerHTML = '<option value="">Seleccione una ciudad</option>';
                ciudades.forEach(c => {
                    const option = document.createElement("option");
                    option.value = c;
                    option.textContent = c;
                    selectCiudad.appendChild(option);
                });
            }

            window.onload = cargarPaises;
        </script>
    </head>
    <body class="container mt-5">
        <h2 class="mb-4">Elecciones Ciudadanas 2025</h2>
        <form method="post" action="/enviar_voto">
            <input type="hidden" name="numero" value="{{ numero }}">

            <div class="mb-3">
                <label class="form-label">Elige tu candidato:</label>
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="candidato" value="Candidato A" required>
                    <label class="form-check-label">Candidato A</label>
                </div>
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="candidato" value="Candidato B">
                    <label class="form-check-label">Candidato B</label>
                </div>
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="candidato" value="Candidato C">
                    <label class="form-check-label">Candidato C</label>
                </div>
            </div>

            <div class="mb-3">
                <label for="pais" class="form-label">País:</label>
                <select class="form-select" id="pais" name="pais" required>
                    <option value="">Seleccione un país</option>
                </select>
            </div>

            <div class="mb-3">
                <label for="ciudad" class="form-label">Ciudad:</label>
                <select class="form-select" id="ciudad" name="ciudad" required>
                    <option value="">Seleccione una ciudad</option>
                </select>
            </div>

            <button type="submit" class="btn btn-primary">Votar</button>
        </form>
    </body>
    </html>
    '''
    return render_template_string(html, numero=numero)

# ---------------------------
# Ruta: Procesamiento del voto
# ---------------------------
@app.route('/enviar_voto', methods=['POST'])
def enviar_voto():
    numero = request.form.get('numero')
    candidato = request.form.get('candidato')
    pais = request.form.get('pais')
    ciudad = request.form.get('ciudad')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if numero in votos_registrados:
        return "Ya registramos tu voto."

    # Guardar todos los datos del votante
    votos_registrados[numero] = {
        "candidato": candidato,
        "pais": pais,
        "ciudad": ciudad,
        "ip": ip,
        "hora": hora
    }

    return f"Gracias por tu voto. Has elegido: {candidato}.<br>Ubicación: {ciudad}, {pais}"

# ---------------------------
# Ruta: Respuesta automática por WhatsApp
# ---------------------------
@app.route('/whatsapp', methods=['POST'])
def whatsapp_reply():
    sender = request.values.get('From', '')
    link_votacion = f"https://votacion-whatsapp.onrender.com/votar?numero={sender}"

    response = MessagingResponse()
    msg = response.message()
    msg.body(f"Hola, gracias por participar en la votación.\n\nHaz clic para votar:\n{link_votacion}")
    return str(response)

# ---------------------------
# Ejecutar la app localmente
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
