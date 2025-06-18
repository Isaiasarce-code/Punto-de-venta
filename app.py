from flask import Flask, request, render_template, redirect, url_for, flash

import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# app = Flask(__name__)

app = Flask(__name__)
app.secret_key = 'alguna_clave_secreta_segura'


# === CONFIGURACIÓN DE GOOGLE SHEETS ===
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = 'gleaming-abacus-436217-u3-533323be62ce.json'  # Subir a Render como archivo secreto o variable
SHEET_NAME = 'CRUZVERDE'    # Nombre visible en Google Sheets

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
    nueva_venta = [
        str(codigo),
        str(descripcion),
        float(precio),
        int(cantidad),
        float(total)
    ]
    ventas.append_row(nueva_venta)

 
# === RUTAS WEB ===
@app.route('/', methods=['GET', 'POST'])
def buscar_producto():
    resultado = None
    error = None

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip().lower()
        descripcion = request.form.get('descripcion', '').strip().lower()

        inventario = cargar_inventario()
        if codigo:
            resultado = inventario[inventario['codigo'].astype(str).str.lower() == codigo]
        elif descripcion:
            resultado = inventario[inventario['descripcion'].str.lower().str.contains(descripcion)]

        if resultado is not None and resultado.empty:
            error = "Producto no encontrado."

    return render_template('buscar.html', productos=resultado, error=error)
@app.route('/vender', methods=['POST'])
def vender_producto():
    try:
        productos_seleccionados = request.form.getlist('producto')
        if not productos_seleccionados:
            flash("⚠️ No seleccionaste ningún producto.")
            return redirect(url_for('buscar_producto'))

        inventario = cargar_inventario()
        hoja = conectar_hoja()
        total_final = 0

        for i in productos_seleccionados:
            codigo = request.form.get(f'codigo_{i}')
            descripcion = request.form.get(f'descripcion_{i}')
            precio = float(request.form.get(f'precio_{i}'))
            cantidad_vendida = int(request.form.get(f'cantidad_{i}'))

            idx = inventario[inventario['codigo'].astype(str) == codigo].index
            if not idx.empty:
                row = idx[0]
                disponible = int(inventario.loc[row, 'cantidad'])
                if cantidad_vendida <= disponible:
                    inventario.at[row, 'cantidad'] = disponible - cantidad_vendida

                    # Registrar venta
                    total = precio * cantidad_vendida
                    total_final += total
                    ventas = hoja.worksheet('Ventas')
                    ventas.append_row([
                        str(codigo),
                        str(descripcion),
                        precio,
                        cantidad_vendida,
                        total
                    ])
                else:
                    flash(f"❌ No hay suficiente stock para {descripcion}.")
            else:
                flash(f"❌ Producto no encontrado: {descripcion}")

        guardar_inventario(inventario)
        flash(f"✅ Venta registrada por un total de ${total_final:.2f}")
        return redirect(url_for('buscar_producto'))

    except Exception as e:
        flash(f"💥 Error inesperado: {e}")
        return redirect(url_for('buscar_producto'))



if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
