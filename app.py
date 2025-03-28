from flask import Flask, request, render_template, redirect
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeSerializer, BadSignature
import os
import requests
import phonenumbers
from phonenumbers import geocoder, carrier, PhoneNumberFormat, region_code_for_country_code, COUNTRY_CODE_TO_REGION_CODE
from phonenumbers import geocoder, carrier

# COdigo Funcional
# ---------------------------
# Inicialización de la aplicación Flask
# ---------------------------
app = Flask(__name__)
SECRET_KEY = os.environ.get("SECRET_KEY", "clave-secreta-segura")
serializer = URLSafeSerializer(SECRET_KEY)
IPQUALITY_API_KEY = os.environ.get("IPQUALITY_API_KEY")

# ---------------------------
# Configuración de la base de datos PostgreSQL
# ---------------------------
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------------
# Modelo de tabla: Voto
# ---------------------------
class Voto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True, nullable=False)
    ci = db.Column(db.BigInteger, nullable=False)
    candidato = db.Column(db.String(100), nullable=False)
    pais = db.Column(db.String(100), nullable=False)
    ciudad = db.Column(db.String(100), nullable=False)
    dia_nacimiento = db.Column(db.Integer, nullable=False)
    mes_nacimiento = db.Column(db.Integer, nullable=False)
    anio_nacimiento = db.Column(db.Integer, nullable=False)
    latitud = db.Column(db.Float, nullable=True)
    longitud = db.Column(db.Float, nullable=True)
    ip = db.Column(db.String(50), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)

# ---------------------------
# Crear tabla si no existe
# ---------------------------
with app.app_context():
    db.create_all()

# ---------------------------
# Función para verificar IP con IPQualityScore
# ---------------------------
def ip_es_vpn(ip):
    if not IPQUALITY_API_KEY or not ip:
        return False
    try:
        url = f"https://ipqualityscore.com/api/json/ip/{IPQUALITY_API_KEY}/{ip}"
        res = requests.get(url)
        data = res.json()
        return data.get("proxy") or data.get("vpn") or data.get("tor")
    except:
        return False

# ---------------------------
# Página de inicio
# ---------------------------
@app.route('/')
def index():
    return "Bienvenido al sistema de votación. Este enlace debe ser accedido desde WhatsApp."

# ---------------------------
# Página de votación protegida con token cifrado
# ---------------------------
@app.route('/votar')
def votar():
    token = request.args.get('token')
    if not token:
        return "Acceso no válido."

    try:
        numero = serializer.loads(token)
    except BadSignature:
        return "Enlace inválido o alterado."

    voto_existente = Voto.query.filter_by(numero=numero).first()
    if voto_existente:
        return f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
          <meta charset="UTF-8">
          <title>Voto ya registrado</title>
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
          <style>
            body {{
              background-color: #f8f9fa;
            }}
            .mensaje-wrapper {{
              max-width: 700px;
              margin: 60px auto;
              padding: 30px;
              background: #fff;
              border-radius: 8px;
              box-shadow: 0 0 10px rgba(0,0,0,0.05);
              text-align: center;
            }}
            .mensaje-wrapper h3 {{
              color: #dc3545;
            }}
          </style>
        </head>
        <body>
          <div class="mensaje-wrapper">
            <h3>Voto ya registrado</h3>
            <p class="mt-3 fs-5">
              Nuestro sistema ha detectado que este número de WhatsApp ya ha emitido su voto.
            </p>
            <p class="text-muted">
              Agradecemos tu participación en este proceso democrático.
            </p>
            <hr>
            <p class="text-secondary">Si crees que esto es un error, por favor contacta con el equipo organizador.</p>
          </div>
        </body>
        </html>
        """


    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip_es_vpn(ip):
        return "No se permite votar desde conexiones de VPN o proxy. Por favor, desactiva tu VPN."

    votos_misma_ip = Voto.query.filter_by(ip=ip).count()
    if votos_misma_ip >= 1:
        return "Se ha alcanzado el límite de votos permitidos desde esta conexión."

    return render_template("votar.html", numero=numero)

# ---------------------------
# Procesar el voto
# ---------------------------
@app.route('/enviar_voto', methods=['POST'])
def enviar_voto():
    numero = request.form.get('numero')
    ci = request.form.get('ci')
    candidato = request.form.get('candidato')
    pais = request.form.get('pais')
    ciudad = request.form.get('ciudad')
    dia = request.form.get('dia_nacimiento')
    mes = request.form.get('mes_nacimiento')
    anio = request.form.get('anio_nacimiento')
    lat = request.form.get('latitud')
    lon = request.form.get('longitud')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if not numero:
        return "Error: el número de WhatsApp es obligatorio."
    if not ci:
        return "Error: el número de carnet de identidad es obligatorio."
    if not pais:
        return "Error: el país es obligatorio."
    if not ciudad:
        return "Error: la ciudad es obligatoria."
    if not dia:
        return "Error: el día de nacimiento es obligatorio."
    if not mes:
        return "Error: el mes de nacimiento es obligatorio."
    if not anio:
        return "Error: el año de nacimiento es obligatorio."
    if not candidato:
        return "Error: debes seleccionar un candidato."

    if Voto.query.filter_by(numero=numero).first():
        return "Ya registramos tu voto."
    if ip_es_vpn(ip):
        return "Voto denegado. No se permite votar desde una VPN o proxy."
    votos_misma_ip = Voto.query.filter_by(ip=ip).count()
    if votos_misma_ip >= 1:
        return "Se ha alcanzado el límite de votos permitidos desde esta conexión."

    nuevo_voto = Voto(
        numero=numero,
        ci=int(ci),
        candidato=candidato,
        pais=pais,
        ciudad=ciudad,
        dia_nacimiento=int(dia),
        mes_nacimiento=int(mes),
        anio_nacimiento=int(anio),
        latitud=float(lat) if lat else None,
        longitud=float(lon) if lon else None,
        ip=ip
    )
    db.session.add(nuevo_voto)
    db.session.commit()

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Voto registrado</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{
                background-color: #f8f9fa;
                padding-top: 50px;
            }}
            .card-confirmacion {{
                max-width: 600px;
                margin: auto;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 0 12px rgba(0,0,0,0.08);
                background-color: #fff;
            }}
            .titulo {{
                color: #198754;
                font-weight: bold;
            }}
            .detalle {{
                font-size: 1.1rem;
            }}
        </style>
    </head>
    <body>
        <div class="card card-confirmacion text-center">
            <h3 class="titulo mb-4">¡Tu voto ha sido registrado exitosamente!</h3>
            <div class="detalle text-start">
                <p><strong>Candidato elegido:</strong> {candidato}</p>
                <p><strong>Número de WhatsApp:</strong> {numero}</p>
                <p><strong>Carnet de Identidad:</strong> {ci}</p>
                <p><strong>Fecha de Nacimiento:</strong> {dia}/{mes}/{anio}</p>
                <p><strong>Ubicación:</strong> {ciudad}, {pais}</p>
            </div>
            <hr class="my-4">
            <p class="text-muted">Gracias por participar en las <strong>Elecciones Ciudadanas 2025</strong>.</p>
            <p class="text-muted">Tu voz ha sido registrada y cuenta para el futuro democrático de Bolivia.</p>
        </div>
    </body>
    </html>
    """



# ---------------------------
# Enviar mensaje con link cifrado vía WhatsApp
# ---------------------------
@app.route('/whatsapp', methods=['POST'])
def whatsapp_reply():
    sender = request.values.get('From', '')
    numero = sender.replace("whatsapp:", "").strip()

    token = serializer.dumps(numero)
    link_votacion = f"https://primariasbunker.org/votar?token={token}"

    response = MessagingResponse()
    msg = response.message()
    msg.body(f"Hola, gracias por ser parte de este proceso democrático.\n\n"
             f"Haz clic en el siguiente enlace para emitir tu voto en las Votaciones Primarias Bolivia 2025:\n"
             f"{link_votacion}")
    return str(response)


# ---------------------------
# Eliminar voto (para pruebas)
# ---------------------------
@app.route('/borrar_voto')
def borrar_voto():
    numero = request.args.get('numero')
    if not numero:
        return "Falta el número. Usa /borrar_voto?numero=whatsapp:+591XXXXXXXX"
    voto = Voto.query.filter_by(numero=numero).first()
    if voto:
        db.session.delete(voto)
        db.session.commit()
        return f"Voto del número {numero} eliminado correctamente."
    else:
        return "No se encontró ningún voto con ese número."

# ---------------------------
# Rutas para desarrollo
# ---------------------------
@app.route('/eliminar_tabla_voto')
def eliminar_tabla_voto():
    try:
        Voto.__table__.drop(db.engine)
        return "La tabla 'voto' ha sido eliminada correctamente."
    except Exception as e:
        return f"Error al eliminar la tabla: {str(e)}"

@app.route('/crear_tabla_voto')
def crear_tabla_voto():
    try:
        with app.app_context():
            db.create_all()
        return "La tabla 'voto' ha sido creada exitosamente."
    except Exception as e:
        return f"Error al crear la tabla: {str(e)}"




@app.route('/generar_link', methods=['GET', 'POST'])
def generar_link():
    if request.method == 'POST':
        pais = request.form.get('pais')
        numero_local = request.form.get('numero_local')

        if not pais or not numero_local:
            return "Por favor, selecciona un país e ingresa tu número."

        codigo_pais = PAISES_CODIGOS.get(pais)
        if not codigo_pais:
            return "País no soportado o inválido."

        numero_completo = f"{codigo_pais}{numero_local.strip()}"
        token = serializer.dumps(numero_completo)
        return redirect(f"/votar?token={token}")

    opciones = ''.join([f"<option value='{p}'>{p}</option>" for p in PAISES_CODIGOS.keys()])

return """
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Iniciar Votación - Primarias Bunker</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/css/select2.min.css" rel="stylesheet" />
  <style>
    body {
      background-color: #f4f6f9;
      padding-top: 60px;
    }
    .card {
      max-width: 550px;
      margin: auto;
      padding: 30px;
      border-radius: 12px;
      background: #ffffff;
      box-shadow: 0 0 15px rgba(0,0,0,0.06);
    }
    .logo {
      width: 100px;
      margin: 0 auto 20px;
      display: block;
    }
    .select2-container .select2-selection--single {
      height: 38px;
    }
  </style>
</head>
<body>
  <div class="card text-center">
    <img src="/static/img/logo.png" alt="Primarias Bunker" class="logo">
    <h3 class="mb-3">Participa en las Elecciones Primarias 2025</h3>
    <p class="text-muted">
      Para emitir tu voto, selecciona tu país y número de WhatsApp. Este paso nos permite generar un enlace único para garantizar que cada persona vote solo una vez.
    </p>
    <form method="POST" onsubmit="return validarFormulario()">
      <div class="mb-3 text-start">
        <label for="pais" class="form-label">País</label>
        <select id="pais" class="form-select" required></select>
      </div>
      <div class="mb-3 text-start">
        <label for="numero" class="form-label">Número de WhatsApp</label>
        <div class="input-group">
          <span class="input-group-text" id="codigo">+000</span>
          <input type="tel" id="numero" class="form-control" placeholder="Ej. 70000000" required>
        </div>
        <small class="text-muted">Ingresa tu número sin el código del país</small>
      </div>
      <button type="submit" class="btn btn-primary w-100">Generar Enlace de Votación</button>
    </form>
    <hr class="my-4">
    <footer class="text-muted small">
      &copy; 2025 Primarias Bunker<br>
      Participación ciudadana por un futuro democrático
    </footer>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/select2@4.1.0-rc.0/dist/js/select2.min.js"></script>
  <script>
    let paises = [];

    async function cargarPaises() {
      const res = await fetch("https://countriesnow.space/api/v0.1/countries/codes");
      const data = await res.json();
      paises = data.data;
      const select = $('#pais');
      select.append('<option value="">Selecciona un país</option>');
      paises.forEach(p => {
        select.append(new Option(p.name + ' (+' + p.dial_code + ')', p.dial_code));
      });
      select.select2({ placeholder: "Selecciona un país" });
    }

    function validarFormulario() {
      const codigo = document.getElementById('codigo').textContent;
      const numero = document.getElementById('numero').value.trim();
      if (!numero.match(/^[0-9]{6,15}$/)) {
        alert("Número inválido. Por favor, verifica el formato.");
        return false;
      }

      const campo = document.createElement("input");
      campo.type = "hidden";
      campo.name = "numero";
      campo.value = codigo + numero;
      document.querySelector("form").appendChild(campo);
      return true;
    }

    $(document).ready(() => {
      cargarPaises();
      $('#pais').on('change', function() {
        const codigo = $(this).val();
        $('#codigo').text("+" + codigo);
      });
    });
  </script>
</body>
</html>
"""




PAISES_CODIGOS = {
    "Bolivia": "+591",
    "Argentina": "+54",
    "Chile": "+56",
    "Perú": "+51",
    "México": "+52",
    "Colombia": "+57",
    "España": "+34",
    "Estados Unidos": "+1",
    "Paraguay": "+595",
    "Brasil": "+55",
    "Ecuador": "+593"
    # Puedes agregar más si lo deseas
}

# ---------------------------
# Ejecutar la app localmente
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
