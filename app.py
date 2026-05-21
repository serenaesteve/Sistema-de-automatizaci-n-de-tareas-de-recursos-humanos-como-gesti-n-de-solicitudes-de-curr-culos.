import os
import json
import uuid
import requests
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "scurriculums-secret-2026")

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"
DB_PATH = "database.db"

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ─── DATABASE ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'rrhh',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        position TEXT NOT NULL,
        email TEXT,
        phone TEXT,
        linkedin TEXT,
        location TEXT,
        salary TEXT,
        experience TEXT,
        education TEXT,
        skills TEXT,
        summary TEXT,
        score INTEGER DEFAULT 0,
        status TEXT DEFAULT 'revisar',
        phase TEXT DEFAULT 'Revisión CV',
        notes TEXT DEFAULT '',
        starred INTEGER DEFAULT 0,
        pdf_path TEXT,
        ai_report TEXT,
        applied_date TEXT DEFAULT CURRENT_DATE,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        employee TEXT NOT NULL,
        department TEXT NOT NULL,
        days INTEGER DEFAULT 1,
        date_from TEXT,
        date_to TEXT,
        note TEXT DEFAULT '',
        status TEXT DEFAULT 'pendiente',
        ai_recommendation TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_DATE,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS request_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        request_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        reason TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(request_id) REFERENCES requests(id)
    )""")

    # Seed demo user
    try:
        c.execute("INSERT INTO users (name, email, password, role) VALUES (?,?,?,?)",
                  ("Admin RRHH", "admin@empresa.com",
                   generate_password_hash("admin123"), "admin"))
        # Seed demo candidates
        demo_candidates = [
            (1,"Alejandro Vega","Desarrollador Full Stack","a.vega@gmail.com","+34 611 000 001","linkedin.com/in/alejandrovega","Madrid","48.000–55.000€","5 años","Grado Informática – UPM","React,Node.js,Python,SQL,Docker","Senior con experiencia en microservicios y CI/CD.",92,"top","Entrevista técnica","",1,None,"","2026-04-18"),
            (1,"Sofía Herrera","Diseñadora UX/UI","s.herrera@gmail.com","+34 622 000 002","linkedin.com/in/sofiaherrera","Barcelona","40.000–46.000€","4 años","Diseño Gráfico – ESNE","Figma,Sketch,CSS,User Research","Portafolio diverso en apps móviles y SaaS B2B.",88,"top","Primera entrevista","Muy buena comunicación",1,None,"","2026-04-19"),
            (1,"Miguel Torres","Desarrollador Full Stack","m.torres@gmail.com","+34 633 000 003","linkedin.com/in/migueltorres","Valencia","30.000–36.000€","2 años","FP Superior DAM – TAME Formación","Vue.js,PHP,MySQL,Laravel","Junior con buena base técnica y proyectos propios en GitHub.",71,"revisar","Revisión CV","",0,None,"","2026-04-20"),
            (1,"Carmen Díaz","Analista de Datos","c.diaz@gmail.com","+34 644 000 004","linkedin.com/in/carmendiaz","Madrid","36.000–42.000€","3 años","Estadística – UCM","Excel,Power BI,SQL,Python básico","Experiencia en análisis descriptivo y dashboards.",65,"revisar","Revisión CV","",0,None,"","2026-04-17"),
            (1,"Roberto Jiménez","Desarrollador Full Stack","r.jimenez@gmail.com","+34 655 000 005","","Sevilla","Sin especificar","6 meses","Sin titulación acreditada","HTML,CSS","Perfil muy junior sin experiencia profesional.",44,"descartado","Descartado","",0,None,"","2026-04-16"),
            (1,"David Castillo","DevOps Engineer","d.castillo@gmail.com","+34 677 000 007","linkedin.com/in/davidcastillo","Barcelona","52.000–60.000€","6 años","Ingeniería Telecomunicaciones – UPC","Kubernetes,Terraform,AWS,CI/CD,Linux","Especialista en infraestructura cloud.",85,"top","Entrevista técnica","",1,None,"","2026-04-22"),
        ]
        for d in demo_candidates:
            c.execute("""INSERT INTO candidates
                (user_id,name,position,email,phone,linkedin,location,salary,experience,education,skills,summary,score,status,phase,notes,starred,pdf_path,ai_report,applied_date)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", d)
        # Seed demo requests
        demo_requests = [
            (1,"Vacaciones","María López","Tecnología",5,"2026-05-01","2026-05-07","Viaje familiar planificado","pendiente",""),
            (1,"Permiso médico","Carlos Ruiz","Producto",1,"2026-04-19","2026-04-19","Cita especialista","aprobada",""),
            (1,"Teletrabajo","Ana Martínez","Operaciones",3,"2026-04-28","2026-04-30","","pendiente",""),
            (1,"Formación","Pedro Sánchez","BI",2,"2026-04-25","2026-04-26","Curso Python avanzado","rechazada",""),
            (1,"Vacaciones","Laura Fernández","Marketing",10,"2026-06-01","2026-06-12","","pendiente",""),
        ]
        for r in demo_requests:
            c.execute("""INSERT INTO requests (user_id,type,employee,department,days,date_from,date_to,note,status,ai_recommendation)
                VALUES (?,?,?,?,?,?,?,?,?,?)""", r)
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()


# ─── AUTH ────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── OLLAMA ──────────────────────────────────────────────────────────────────

def ask_ollama(prompt, system=""):
    full_prompt = f"{system}\n\n{prompt}" if system else prompt
    try:
        res = requests.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": full_prompt,
            "stream": False
        }, timeout=999)
        data = res.json()
        return data.get("response", "Sin respuesta de la IA.")
    except requests.exceptions.ConnectionError:
        return "⚠️ No se puede conectar con Ollama. Asegúrate de que está ejecutándose con: ollama serve"
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

def extract_pdf_text(pdf_path):
    """Extract text from PDF using PyMuPDF if available, else pdfminer"""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()
        return text.strip()
    except ImportError:
        pass
    try:
        from pdfminer.high_level import extract_text
        return extract_text(pdf_path).strip()
    except ImportError:
        return None


# ─── ROUTES: AUTH ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        conn.close()
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_role"] = user["role"]
            return redirect(url_for("dashboard"))
        flash("Email o contraseña incorrectos", "error")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if not name or not email or not password:
            flash("Todos los campos son obligatorios", "error")
            return render_template("register.html")
        if password != confirm:
            flash("Las contraseñas no coinciden", "error")
            return render_template("register.html")
        if len(password) < 6:
            flash("La contraseña debe tener al menos 6 caracteres", "error")
            return render_template("register.html")
        conn = get_db()
        try:
            conn.execute("INSERT INTO users (name, email, password) VALUES (?,?,?)",
                         (name, email, generate_password_hash(password)))
            conn.commit()
            flash("Cuenta creada correctamente. Inicia sesión.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Ese email ya está registrado", "error")
        finally:
            conn.close()
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── ROUTES: PAGES ────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()
    uid = session["user_id"]
    cvs = conn.execute("SELECT * FROM candidates WHERE user_id=?", (uid,)).fetchall()
    reqs = conn.execute("SELECT * FROM requests WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (uid,)).fetchall()
    conn.close()

    top = sum(1 for c in cvs if c["status"] == "top")
    pending = sum(1 for r in reqs if r["status"] == "pendiente")
    phases = {}
    for c in cvs:
        p = c["phase"]
        phases[p] = phases.get(p, 0) + 1

    return render_template("dashboard.html",
        cvs=cvs, recent_requests=reqs,
        total_cvs=len(cvs), top=top, pending=pending, phases=phases)

@app.route("/curriculos")
@login_required
def curriculos():
    conn = get_db()
    uid = session["user_id"]
    status_filter = request.args.get("status", "todas")
    pos_filter = request.args.get("pos", "")
    search = request.args.get("q", "")

    query = "SELECT * FROM candidates WHERE user_id=?"
    params = [uid]
    if status_filter != "todas":
        query += " AND status=?"
        params.append(status_filter)
    if pos_filter:
        query += " AND position=?"
        params.append(pos_filter)
    if search:
        query += " AND (name LIKE ? OR position LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    query += " ORDER BY score DESC"

    cvs = conn.execute(query, params).fetchall()
    all_positions = conn.execute("SELECT DISTINCT position FROM candidates WHERE user_id=?", (uid,)).fetchall()
    conn.close()

    return render_template("curriculos.html", cvs=cvs, all_positions=all_positions,
                           status_filter=status_filter, pos_filter=pos_filter, search=search)

@app.route("/curriculos/<int:cv_id>")
@login_required
def cv_detail(cv_id):
    conn = get_db()
    cv = conn.execute("SELECT * FROM candidates WHERE id=? AND user_id=?",
                      (cv_id, session["user_id"])).fetchone()
    conn.close()
    if not cv:
        return redirect(url_for("curriculos"))
    return render_template("cv_detail.html", cv=cv)

@app.route("/curriculos/add", methods=["GET", "POST"])
@login_required
def add_cv():
    if request.method == "POST":
        conn = get_db()
        conn.execute("""INSERT INTO candidates
            (user_id,name,position,email,phone,linkedin,location,salary,experience,education,skills,summary,score,status,phase,applied_date)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            session["user_id"],
            request.form.get("name"),
            request.form.get("position"),
            request.form.get("email",""),
            request.form.get("phone",""),
            request.form.get("linkedin",""),
            request.form.get("location",""),
            request.form.get("salary",""),
            request.form.get("experience",""),
            request.form.get("education",""),
            request.form.get("skills",""),
            request.form.get("summary",""),
            int(request.form.get("score",50)),
            request.form.get("status","revisar"),
            "Revisión CV",
            datetime.now().strftime("%Y-%m-%d")
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("curriculos"))
    return render_template("add_cv.html")

@app.route("/solicitudes")
@login_required
def solicitudes():
    conn = get_db()
    uid = session["user_id"]
    status_filter = request.args.get("status", "todas")
    query = "SELECT * FROM requests WHERE user_id=?"
    params = [uid]
    if status_filter != "todas":
        query += " AND status=?"
        params.append(status_filter)
    query += " ORDER BY created_at DESC"
    reqs = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("solicitudes.html", requests=reqs, status_filter=status_filter)

@app.route("/solicitudes/add", methods=["GET", "POST"])
@login_required
def add_solicitud():
    if request.method == "POST":
        conn = get_db()
        conn.execute("""INSERT INTO requests (user_id,type,employee,department,days,date_from,date_to,note,status)
            VALUES (?,?,?,?,?,?,?,?,?)""", (
            session["user_id"],
            request.form.get("type"),
            request.form.get("employee"),
            request.form.get("department"),
            int(request.form.get("days", 1)),
            request.form.get("date_from",""),
            request.form.get("date_to",""),
            request.form.get("note",""),
            "pendiente"
        ))
        conn.commit()
        conn.close()
        return redirect(url_for("solicitudes"))
    return render_template("add_solicitud.html")

@app.route("/asistente")
@login_required
def asistente():
    return render_template("asistente.html")


# ─── ROUTES: API ──────────────────────────────────────────────────────────────

@app.route("/api/cv/<int:cv_id>/phase", methods=["POST"])
@login_required
def update_phase(cv_id):
    phase = request.json.get("phase")
    status_map = {"Descartado": "descartado", "Incorporado": "top"}
    conn = get_db()
    cv = conn.execute("SELECT * FROM candidates WHERE id=? AND user_id=?",
                      (cv_id, session["user_id"])).fetchone()
    if not cv:
        conn.close()
        return jsonify({"error": "No encontrado"}), 404
    new_status = status_map.get(phase, cv["status"])
    conn.execute("UPDATE candidates SET phase=?, status=? WHERE id=?", (phase, new_status, cv_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "phase": phase, "status": new_status})

@app.route("/api/cv/<int:cv_id>/star", methods=["POST"])
@login_required
def toggle_star(cv_id):
    conn = get_db()
    cv = conn.execute("SELECT starred FROM candidates WHERE id=? AND user_id=?",
                      (cv_id, session["user_id"])).fetchone()
    if not cv:
        conn.close()
        return jsonify({"error": "No encontrado"}), 404
    new_val = 0 if cv["starred"] else 1
    conn.execute("UPDATE candidates SET starred=? WHERE id=?", (new_val, cv_id))
    conn.commit()
    conn.close()
    return jsonify({"starred": bool(new_val)})

@app.route("/api/cv/<int:cv_id>/note", methods=["POST"])
@login_required
def update_note(cv_id):
    note = request.json.get("note", "")
    conn = get_db()
    conn.execute("UPDATE candidates SET notes=? WHERE id=? AND user_id=?",
                 (note, cv_id, session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/cv/<int:cv_id>/report", methods=["POST"])
@login_required
def generate_report(cv_id):
    conn = get_db()
    cv = conn.execute("SELECT * FROM candidates WHERE id=? AND user_id=?",
                      (cv_id, session["user_id"])).fetchone()
    conn.close()
    if not cv:
        return jsonify({"error": "No encontrado"}), 404

    system = "Eres un experto en selección de personal en España. Genera informes profesionales detallados en español."
    prompt = f"""Genera un informe de evaluación completo para este candidato:
Nombre: {cv['name']}
Puesto: {cv['position']}
Experiencia: {cv['experience']}
Educación: {cv['education']}
Habilidades: {cv['skills']}
Puntuación IA: {cv['score']}/100
Fase actual: {cv['phase']}
Resumen: {cv['summary']}

Incluye:
1) Evaluación general del perfil
2) Puntos fuertes (mínimo 3)
3) Áreas de mejora
4) Recomendación de avance en el proceso
5) Preguntas sugeridas para la entrevista (mínimo 4)
6) Conclusión final"""

    report = ask_ollama(prompt, system)
    conn = get_db()
    conn.execute("UPDATE candidates SET ai_report=? WHERE id=?", (report, cv_id))
    conn.commit()
    conn.close()
    return jsonify({"report": report})

@app.route("/api/cv/upload-pdf", methods=["POST"])
@login_required
def upload_pdf():
    if "pdf" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400
    file = request.files["pdf"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"error": "Archivo no válido. Solo se permiten PDFs"}), 400

    filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
    pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(pdf_path)

    # Extract text
    text = extract_pdf_text(pdf_path)
    if not text:
        return jsonify({"error": "No se pudo extraer texto del PDF. Instala PyMuPDF: pip install pymupdf"}), 400

    # Analyze with Ollama
    system = "Eres un experto en RRHH y selección de personal en España. Analiza currículos de forma objetiva y profesional. Responde siempre en español."
    prompt = f"""Analiza este currículo y proporciona un análisis estructurado:

1) RESUMEN EJECUTIVO (2-3 frases)
2) PUNTOS FUERTES (lista)
3) PUNTOS DÉBILES (lista)
4) ADECUACIÓN AL MERCADO ESPAÑOL
5) DATOS EXTRAÍDOS:
   - Nombre completo del candidato
   - Puesto o perfil principal
   - Años de experiencia
   - Educación/Formación más alta
   - Habilidades principales (lista separada por comas)
   - Ubicación (si aparece)
6) RECOMENDACIÓN: top candidato / revisar / descartar
7) PUNTUACIÓN: XX/100

CURRÍCULO:
{text[:4000]}"""

    analysis = ask_ollama(prompt, system)

    # Try to extract score
    score = 60
    for line in analysis.split("\n"):
        if "PUNTUACIÓN:" in line.upper() or "PUNTUACION:" in line.upper():
            import re
            nums = re.findall(r'\d+', line)
            if nums:
                score = min(100, max(0, int(nums[0])))
                break

    status = "top" if score >= 80 else "revisar" if score >= 60 else "descartado"

    return jsonify({
        "analysis": analysis,
        "score": score,
        "status": status,
        "text_preview": text[:500],
        "pdf_filename": filename
    })

@app.route("/api/cv/save-from-pdf", methods=["POST"])
@login_required
def save_from_pdf():
    data = request.json
    conn = get_db()
    conn.execute("""INSERT INTO candidates
        (user_id,name,position,email,phone,linkedin,location,salary,experience,education,skills,summary,score,status,phase,ai_report,pdf_path,applied_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
        session["user_id"],
        data.get("name", "Candidato sin nombre"),
        data.get("position", "Sin especificar"),
        data.get("email", ""),
        data.get("phone", ""),
        data.get("linkedin", ""),
        data.get("location", ""),
        data.get("salary", ""),
        data.get("experience", ""),
        data.get("education", ""),
        data.get("skills", ""),
        data.get("summary", ""),
        data.get("score", 60),
        data.get("status", "revisar"),
        "Revisión CV",
        data.get("analysis", ""),
        data.get("pdf_filename", ""),
        datetime.now().strftime("%Y-%m-%d")
    ))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/request/<int:req_id>/status", methods=["POST"])
@login_required
def update_request_status(req_id):
    status = request.json.get("status")
    reason = request.json.get("reason", "")
    conn = get_db()
    conn.execute("UPDATE requests SET status=? WHERE id=? AND user_id=?",
                 (status, req_id, session["user_id"]))
    conn.execute("INSERT INTO request_history (request_id, action, reason) VALUES (?,?,?)",
                 (req_id, status, reason))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})

@app.route("/api/request/<int:req_id>/ai", methods=["POST"])
@login_required
def request_ai(req_id):
    conn = get_db()
    req = conn.execute("SELECT * FROM requests WHERE id=? AND user_id=?",
                       (req_id, session["user_id"])).fetchone()
    conn.close()
    if not req:
        return jsonify({"error": "No encontrado"}), 404

    system = "Eres un experto en RRHH español con amplio conocimiento del Estatuto de los Trabajadores. Das recomendaciones claras, breves y fundamentadas."
    prompt = f"""Analiza esta solicitud de RRHH y recomienda si aprobarla o rechazarla:

Tipo: {req['type']}
Empleado: {req['employee']} (Departamento: {req['department']})
Días solicitados: {req['days']} ({req['date_from']} – {req['date_to']})
Nota del empleado: "{req['note'] or 'ninguna'}"
Estado actual: {req['status']}

Proporciona: 1) Recomendación clara (aprobar/rechazar), 2) Justificación legal o de buenas prácticas, 3) Posibles consideraciones adicionales."""

    recommendation = ask_ollama(prompt, system)
    conn = get_db()
    conn.execute("UPDATE requests SET ai_recommendation=? WHERE id=?", (recommendation, req_id))
    conn.commit()
    conn.close()
    return jsonify({"recommendation": recommendation})

@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    message = request.json.get("message", "")
    history = request.json.get("history", [])
    if not message:
        return jsonify({"error": "Mensaje vacío"}), 400

    system = """Eres un asistente experto en Recursos Humanos para empresas españolas.
Ayudas con: gestión de solicitudes, análisis de currículos, políticas de RRHH, legislación laboral española (ET, convenios colectivos, RGPD/LOPDGDD), redacción de comunicados, descripciones de puestos, onboarding, offboarding, evaluaciones del desempeño y planes de formación.
Responde siempre en español, de forma profesional pero cercana. Sé conciso y práctico.
Si te piden plantillas o documentos, proporciónalos directamente y listos para usar."""

    # Build conversation context from history
    context = ""
    for msg in history[-6:]:  # last 3 exchanges
        role = "Usuario" if msg["role"] == "user" else "Asistente"
        context += f"{role}: {msg['content']}\n"
    context += f"Usuario: {message}"

    response = ask_ollama(context, system)
    return jsonify({"response": response})


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
