from flask import Flask, request, render_template, redirect
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from itsdangerous import URLSafeSerializer, BadSignature
import os
import requests
import phonenumbers
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
from flask import Flask, request, redirect
from itsdangerous import URLSafeSerializer
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE, geocoder
from flask import Flask, request, redirect, render_template_string


# --- Configuración base ---
app = Flask(__name__)
serializer = URLSafeSerializer("clave-secreta")
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
    if votos_misma_ip >= 10:
        return "Se ha alcanzado el límite de votos permitidos desde esta conexión."

    return render_template("votar.html", numero=numero)


# --- Función para obtener país + código ---
def obtener_lista_paises():
    paises = {}
    for code, regions in COUNTRY_CODE_TO_REGION_CODE.items():
        for region in regions:
            try:
                nombre = geocoder.description_for_number(phonenumbers.parse(f"+{code}", region), "es")
                if nombre and nombre not in paises:
                    paises[nombre] = f"+{code}"
            except:
                continue
    return dict(sorted(paises.items()))



# ---------------------------
# Ruta para generar link de votación
# ---------------------------
@app.route('/generar_link', methods=['GET', 'POST'])
def generar_link():
    paises_codigos = obtener_lista_paises()

    if request.method == 'POST':
        pais = request.form.get('pais')
        numero = request.form.get('numero')

        if not pais or not numero:
            return "Por favor, selecciona un país e ingresa tu número."

        codigo = paises_codigos.get(pais)
        if not codigo:
            return "País no reconocido."

        numero_completo = f"{codigo}{numero}"
        token = serializer.dumps(numero_completo)
        return redirect(f"/votar?token={token}")

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Iniciar Votación</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background-color: #f4f6f9;
                padding-top: 80px;
            }
            .card {
                max-width: 500px;
                margin: auto;
                padding: 30px;
                border-radius: 10px;
                background: #fff;
                box-shadow: 0 0 12px rgba(0,0,0,0.06);
            }
        </style>
    </head>
    <body>
        <div class="card text-center">
            <h3>Inicio de votación</h3>
            <p class="text-muted">Selecciona tu país e ingresa tu número local:</p>
            <form method="POST">
                <div class="mb-3 text-start">
                    <label class="form-label">País</label>
                    <select name="pais" class="form-select" required>
                        <option value="">Selecciona un país</option>
                        {% for pais, codigo in paises.items() %}
                            <option value="{{ pais }}">{{ pais }} ({{ codigo }})</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="mb-3 text-start">
                    <label class="form-label">Número de WhatsApp (sin código)</label>
                    <input type="tel" name="numero" class="form-control" placeholder="Ej: 70000000" required>
                </div>
                <button type="submit" class="btn btn-primary w-100">Generar enlace</button>
            </form>
        </div>
    </body>
    </html>
    """, paises=paises_codigos)



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
    if votos_misma_ip >= 10:
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

# ---------------------------
# Ejecutar la app localmente
# ---------------------------
if __name__ == '__main__':
    app.run(debug=True)
