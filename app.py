from flask import Flask, request, render_template_string
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import os

app = Flask(__name__)

# ---------------------------
# Configuración de la base de datos PostgreSQL
# ---------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------------
# Modelo de tabla: votos
# ---------------------------
class Voto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True, nullable=False)
    candidato = db.Column(db.String(100), nullable=False)
    pais = db.Column(db.String(100), nullable=False)
    ciudad = db.Column(db.String(100), nullable=False)
    ip = db.Column(db.String(50), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------------------
# Crear tabla si no existe (solo una vez)
# ---------------------------
@app.before_first_request
def crear_tabla():
    db.create_all()

# ---------------------------
# Ruta: Página de votación
# ---------------------------
@app.route('/votar')
def votar():
    numero = request.args.get('numero')
    if not numero:
        return "Acceso no válido"

    voto_existente = Voto.query.filter_by(numero=numero).first()
    if voto_existente:
        return "Este número ya ha votado. Gracias por participar."

    html = '''
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Elecciones Ciudadanas 2025</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />

        <script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>

        <script>
            async function cargarPaises() {
                const res = await fetch("https://countriesnow.space/api/v0.1/countries");
                const data = await res.json();
                const paises = data.data;

                const selectPais = $('#pais');
                paises.forEach(p => {
                    const option = new Option(p.country, p.country, false, false);
                    selectPais.append(option);
                });

                selectPais.trigger('change');

                selectPais.on('change', function () {
                    const paisSeleccionado = $(this).val();
                    cargarCiudades(paisSeleccionado);
                });
            }

            async function cargarCiudades(pais) {
                const selectCiudad = $('#ciudad');
                selectCiudad.empty().append(new Option("Cargando...", "", false, false)).trigger('change');

                const res = await fetch("https://countriesnow.space/api/v0.1/countries/cities", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ country: pais })
                });

                const data = await res.json();
                selectCiudad.empty().append(new Option("Seleccione una ciudad", "", false, false));

                data.data.forEach(c => {
                    const option = new Option(c, c, false, false);
                    selectCiudad.append(option);
                });

                selectCiudad.trigger('change');
            }

            $(document).ready(function () {
                $('#pais').select2({ placeholder: "Seleccione un país", width: '100%' });
                $('#ciudad').select2({ placeholder: "Seleccione una ciudad", width: '100%' });

                cargarPaises();
            });
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
                <select id="pais" name="pais" class="form-select" required>
                    <option></option>
                </select>
            </div>

            <div class="mb-3">
                <label for="ciudad" class="form-label">Ciudad:</label>
                <select id="ciudad" name="ciudad" class="form-select" required>
                    <option></option>
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

    if Voto.query.filter_by(numero=numero).first():
        return "Ya registramos tu voto."

    nuevo_voto = Voto(
        numero=numero,
        candidato=candidato,
        pais=pais,
        ciudad=ciudad,
        ip=ip
    )

    db.session.add(nuevo_voto)
    db.session.commit()

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
# Ejecutar localmente
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
