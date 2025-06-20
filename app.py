from flask import Flask, request, render_template, redirect, url_for, flash, session
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

app = Flask(__name__)
app.secret_key = 'alguna_clave_secreta_segura'


# === CONFIGURACIÓN DE GOOGLE SHEETS ===
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = 'gleaming-abacus-436217-u3-533323be62ce.json'  # Subir a Render como archivo secreto o variable
SHEET_NAME = 'CRUZVERDE'

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
    nueva_venta = [str(codigo), str(descripcion), float(precio), int(cantidad), float(total)]
    ventas.append_row(nueva_venta)


# === RUTA PRINCIPAL ===
@app.route('/', methods=['GET', 'POST'])
def buscar_producto():
    resultado = None
    error = None

    if 'carrito' not in session:
        session['carrito'] = []

    if request.method == 'POST':
        if 'agregar' in request.form:
            # Agregar al carrito
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
            # Búsqueda de producto
            codigo = request.form.get('codigo', '').strip().lower()
            descripcion = request.form.get('descripcion', '').strip().lower()
            inventario = cargar_inventario()

            if codigo:
                resultado = inventario[inventario['codigo'].astype(str).str.lower() == codigo]
            elif descripcion:
                resultado = inventario[inventario['descripcion'].str.lower().str.contains(descripcion)]

            if resultado is not None and resultado.empty:
                error = "Producto no encontrado."

    carrito = session.get('carrito', [])
    total = sum(float(i['precio']) * int(i['cantidad']) for i in carrito if 'precio' in i and 'cantidad' in i)

    return render_template('buscar.html', productos=resultado, error=error, carrito=carrito, total=total)


@app.route('/vender', methods=['POST'])
def vender_producto():
    try:
        carrito = session.get('carrito', [])
        if not carrito:
            flash("⚠️ El carrito está vacío.")
            return redirect(url_for('buscar_producto'))

        inventario = cargar_inventario()
        hoja = conectar_hoja()
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
                    total = precio * cantidad
                    total_final += total
                    hoja.worksheet('Ventas').append_row([
                        str(codigo), str(descripcion), precio, cantidad, total
                    ])
                else:
                    flash(f"❌ Stock insuficiente para {descripcion}.")
            else:
                flash(f"❌ Producto no encontrado: {descripcion}")

        guardar_inventario(inventario)
        session['carrito'] = []
        flash(f"✅ Venta registrada por un total de ${total_final:.2f}")
        return redirect(url_for('buscar_producto'))

    except Exception as e:
        flash(f"💥 Error inesperado: {e}")
        return redirect(url_for('buscar_producto'))


@app.route('/vaciar_carrito', methods=['POST'])
def vaciar_carrito():
    session['carrito'] = []
    flash("🧹 Carrito vaciado correctamente.")
    return redirect(url_for('buscar_producto'))


@app.route('/eliminar_item', methods=['POST'])
def eliminar_item():
    idx = int(request.form['index'])
    carrito = session.get('carrito', [])
    if 0 <= idx < len(carrito):
        del carrito[idx]
        session['carrito'] = carrito
        flash("🗑️ Producto eliminado del carrito.")
    return redirect(url_for('buscar_producto'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
