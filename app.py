from flask import Flask, request, render_template, redirect, url_for, flash, session
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import os
import pytz
from functools import wraps

app = Flask(__name__)
app.secret_key = 'alguna_clave_secreta_segura'

# === CONFIGURACIÓN DE GOOGLE SHEETS ===
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = 'gleaming-abacus-436217-u3-533323be62ce.json'
SHEET_NAME = 'CRUZVERDE'

# === USUARIO Y CONTRASEÑA PARA LOGIN SIMPLE ===
USUARIO_VALIDO = 'admin'
PASSWORD_VALIDO = '1234'

# === DECORADOR PARA PROTEGER RUTAS ===
def login_requerido(f):
    @wraps(f)
    def decorada(*args, **kwargs):
        if not session.get('logueado'):
            flash('🔒 Inicia sesión para continuar.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorada

# === CONEXIÓN A HOJA DE CÁLCULO ===
def conectar_hoja():
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, SCOPE)
    cliente = gspread.authorize(creds)
    hoja = cliente.open(SHEET_NAME)
    return hoja

# === FUNCIONES DE INVENTARIO ===
def cargar_inventario():
    hoja = conectar_hoja()
    datos = hoja.worksheet('Inventario').get_all_records()
    return pd.DataFrame(datos)

def guardar_inventario(df):
    hoja = conectar_hoja()
    ws = hoja.worksheet('Inventario')
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.values.tolist())

def registrar_venta(codigo, descripcion, precio, cantidad):
    hoja = conectar_hoja()
    ventas = hoja.worksheet('Ventas')
    total = float(precio) * int(cantidad)

    tz_mexico = pytz.timezone('America/Mexico_City')
    ahora = datetime.now(tz_mexico)
    fecha = ahora.strftime('%Y-%m-%d')
    hora = ahora.strftime('%H:%M:%S')

    nueva_venta = [str(codigo), str(descripcion), float(precio), int(cantidad), float(total), fecha, hora]
    ventas.append_row(nueva_venta)

# === RUTA DE LOGIN ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        contraseña = request.form['contraseña']
        if usuario == USUARIO_VALIDO and contraseña == PASSWORD_VALIDO:
            session['logueado'] = True
            flash('🔐 Acceso concedido')
            return redirect(url_for('buscar_producto'))
        else:
            flash('❌ Usuario o contraseña incorrectos')
    return render_template('login.html')

# === CERRAR SESIÓN ===
@app.route('/logout')
def logout():
    session.clear()
    flash("🔓 Sesión cerrada.")
    return redirect(url_for('login'))

# === RUTA PRINCIPAL ===
@app.route('/', methods=['GET', 'POST'])
@login_requerido
def buscar_producto():
    resultado = None
    error = None

    if 'carrito' not in session:
        session['carrito'] = []

    if request.method == 'POST':
        if 'agregar' in request.form:
            codigo = request.form['codigo']
            descripcion = request.form['descripcion']
            precio = float(request.form['precio'])
            cantidad = int(request.form['cantidad'])

            inventario = cargar_inventario()
            item = inventario[inventario['codigo'].astype(str) == str(codigo)]

            if not item.empty:
                disponible = int(item.iloc[0]['cantidad'])
                if cantidad <= disponible:
                    producto = {
                        'codigo': codigo,
                        'descripcion': descripcion,
                        'precio': precio,
                        'cantidad': cantidad
                    }
                    session['carrito'].append(producto)
                    session.modified = True
                    flash(f"✅ {descripcion} agregado al carrito.")
                else:
                    flash(f"❌ Solo hay {disponible} unidades disponibles de {descripcion}.")
            else:
                flash("❌ Producto no encontrado en el inventario.")

            return redirect(url_for('buscar_producto'))

        else:
            codigo = request.form.get('codigo', '').strip().lower()
            descripcion = request.form.get('descripcion', '').strip().lower()
            inventario = cargar_inventario()

            tz_mexico = pytz.timezone('America/Mexico_City')
            hoy = datetime.now(tz_mexico).weekday()
            es_oferta = hoy in [0, 3]

            if codigo:
                resultado = inventario[inventario['codigo'].astype(str).str.lower() == codigo]
            elif descripcion:
                resultado = inventario[inventario['descripcion'].str.lower().str.contains(descripcion)]

            if resultado is not None and not resultado.empty and es_oferta:
                resultado = resultado.copy()
                resultado['ahorro'] = resultado['precio'] - resultado['diaoferta']
                resultado['precio'] = resultado['diaoferta']

            if resultado is not None and resultado.empty:
                error = "Producto no encontrado."

    carrito = session.get('carrito', [])
    total = sum(float(i['precio']) * int(i['cantidad']) for i in carrito if 'precio' in i and 'cantidad' in i)
    ahorro_total = 0
    inventario = cargar_inventario()
    for item in carrito:
        fila = inventario[inventario['codigo'].astype(str) == item['codigo']]
        if not fila.empty:
            normal = float(fila.iloc[0]['precio'])
            actual = float(item['precio'])
            ahorro_unitario = max(0, normal - actual)
            ahorro_total += ahorro_unitario * int(item['cantidad'])

    return render_template('buscar.html', productos=resultado, error=error, carrito=carrito, total=total, ahorro_total=ahorro_total)

@app.route('/vender', methods=['POST'])
@login_requerido
def vender_producto():
    try:
        carrito = session.get('carrito', [])
        if not carrito:
            flash("⚠️ El carrito está vacío.")
            return redirect(url_for('buscar_producto'))

        inventario = cargar_inventario()
        total_final = 0

        for item in carrito:
            codigo = item['codigo']
            descripcion = item['descripcion']
            precio = float(item['precio'])
            cantidad = int(item['cantidad'])

            idx = inventario[inventario['codigo'].astype(str) == str(codigo)].index
            if not idx.empty:
                row = idx[0]
                disponible = int(inventario.loc[row, 'cantidad'])
                if cantidad <= disponible:
                    inventario.at[row, 'cantidad'] = disponible - cantidad
                    total_final += precio * cantidad
                    registrar_venta(codigo, descripcion, precio, cantidad)
                else:
                    flash(f"❌ Stock insuficiente para {descripcion}.")
            else:
                flash(f"❌ Producto no encontrado: {descripcion}")

        guardar_inventario(inventario)
        session['ultimo_ticket'] = carrito
        session['carrito'] = []
        flash(f"✅ Venta registrada por un total de ${total_final:.2f}")
        return redirect(url_for('mostrar_ticket'))

    except Exception as e:
        flash(f"💥 Error inesperado: {e}")
        return redirect(url_for('buscar_producto'))

@app.route('/ticket')
@login_requerido
def mostrar_ticket():
    carrito = session.get('ultimo_ticket', [])
    total = sum(float(i['precio']) * int(i['cantidad']) for i in carrito if 'precio' in i and 'cantidad' in i)

    tz_mexico = pytz.timezone('America/Mexico_City')
    ahora = datetime.now(tz_mexico)
    fecha = ahora.strftime('%Y-%m-%d')
    hora = ahora.strftime('%H:%M:%S')

    return render_template('ticket.html', carrito=carrito, total=total, fecha=fecha, hora=hora)

@app.route('/vaciar_carrito', methods=['POST'])
@login_requerido
def vaciar_carrito():
    session['carrito'] = []
    flash("🧹 Carrito vaciado correctamente.")
    return redirect(url_for('buscar_producto'))

@app.route('/eliminar_item', methods=['POST'])
@login_requerido
def eliminar_item():
    idx = int(request.form['index'])
    carrito = session.get('carrito', [])
    if 0 <= idx < len(carrito):
        del carrito[idx]
        session['carrito'] = carrito
        flash("🗑️ Producto eliminado del carrito.")
    return redirect(url_for('buscar_producto'))

@app.route('/modificar_cantidad', methods=['POST'])
@login_requerido
def modificar_cantidad():
    try:
        idx = int(request.form['index'])
        nueva_cantidad = int(request.form['nueva_cantidad'])
        carrito = session.get('carrito', [])
        inventario = cargar_inventario()

        if 0 <= idx < len(carrito):
            producto = carrito[idx]
            codigo = producto['codigo']
            stock = inventario[inventario['codigo'].astype(str) == str(codigo)]

            if not stock.empty:
                disponible = int(stock.iloc[0]['cantidad'])
                if nueva_cantidad <= disponible:
                    carrito[idx]['cantidad'] = nueva_cantidad
                    session['carrito'] = carrito
                    flash("🔁 Cantidad actualizada correctamente.")
                else:
                    flash(f"❌ No puedes solicitar más de {disponible} unidades.")
            else:
                flash("❌ Producto no encontrado en el inventario.")
        else:
            flash("❌ Índice fuera de rango.")
    except Exception as e:
        flash(f"💥 Error al actualizar: {e}")

    return redirect(url_for('buscar_producto'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
