"""Cuentas Coarcun - interfaz. Ejecutar con:  streamlit run app.py"""
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

import core

LOGO = Path(__file__).parent / "logo.png"  # escudo de la corporación (debe estar junto a app.py)

st.set_page_config(page_title="Cuentas Coarcun", page_icon=str(LOGO) if LOGO.exists() else "⚽", layout="wide")


def mostrar_logo(ancho):
    if LOGO.exists():
        st.image(str(LOGO), width=ancho)

core.init_db()
core.codigo_admin()  # crea codigo_admin.txt la primera vez que se abre la app

st.markdown("""
<style>
h1, h2, h3 { color: #0070C0; }
div[data-testid="stMetricValue"] { color: #0070C0; }
.stButton > button[kind="primary"] { background-color: #0070C0; border-color: #0070C0; }
div[data-testid="stImage"] img { border-radius: 12px; }
</style>""", unsafe_allow_html=True)

st.session_state.setdefault("user", None)


# ------------------------------------------------------------ ingreso / registro
def pantalla_ingreso():
    c_logo, c_titulo = st.columns([1, 6], vertical_alignment="center")
    with c_logo:
        mostrar_logo(110)
    with c_titulo:
        st.title("Cuentas Coarcun")
        st.caption("Corporación Arbitral de Cundinamarca")
    t_ing, t_arb, t_adm = st.tabs(["Ingresar", "Primera vez (árbitro)", "Crear administrador"])

    with t_ing, st.form("login"):
        nombre = st.text_input("Nombre completo")
        clave = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Ingresar", type="primary"):
            u = core.autenticar(nombre, clave)
            if u:
                st.session_state.user = u
                st.rerun()
            st.error("Nombre o contraseña incorrectos.")

    with t_arb, st.form("registro_arbitro"):
        st.caption("Escribe tu nombre completo, tal como aparece en las designaciones.")
        nombre = st.text_input("Nombre completo")
        residencia = st.selectbox("Lugar de residencia", core.RESIDENCIAS)
        c1 = st.text_input("Crea tu contraseña (mínimo 6 caracteres)", type="password")
        c2 = st.text_input("Repite la contraseña", type="password")
        forzar = st.checkbox("Mi nombre no aparece en las designaciones todavía, crear mi cuenta de todas formas")
        if st.form_submit_button("Crear mi cuenta", type="primary"):
            if c1 != c2:
                st.error("Las contraseñas no coinciden.")
            else:
                try:
                    core.registrar_arbitro_por_nombre(nombre, c1, residencia, forzar)
                    st.success("Cuenta creada. Ya puedes ingresar en la pestaña «Ingresar».")
                except LookupError:
                    sug = core.sugerir_nombres(nombre)
                    if sug:
                        st.warning("No encontré ese nombre exacto. ¿Eres alguno de estos? "
                                   "Escríbelo exactamente así: " + " · ".join(sug))
                    else:
                        st.warning("Ese nombre no aparece en las designaciones cargadas. Revisa cómo lo escribiste. "
                                   "Si es correcto y aún no te han designado, marca la casilla de arriba para crear la cuenta.")
                except ValueError as e:
                    st.error(str(e))

    with t_adm, st.form("registro_admin"):
        if core.codigo_admin() is None:
            st.error("Falta configurar el código secreto: agrega COARCUN_ADMIN_CODE en los Secrets de la app.")
        elif not core.hay_administradores() and not core.usa_postgres():
            st.info(f"Aún no hay administradores. El código secreto está en el archivo "
                    f"`{core.CODIGO_FILE}` (junto a la app).")
        nombre = st.text_input("Nombre completo del administrador")
        c1 = st.text_input("Contraseña", type="password")
        c2 = st.text_input("Repite la contraseña", type="password")
        codigo = st.text_input("Código secreto de administradores", type="password")
        if st.form_submit_button("Crear administrador", type="primary"):
            if not core.verificar_codigo_admin(codigo):
                st.error("Código secreto incorrecto.")
            elif c1 != c2:
                st.error("Las contraseñas no coinciden.")
            elif not nombre.strip():
                st.error("Escribe tu nombre.")
            else:
                try:
                    core.crear_usuario(nombre, c1, "admin")
                    st.success("Administrador creado. Ya puedes ingresar.")
                except ValueError as e:
                    st.error(str(e))


# ------------------------------------------------------------- cuenta de cobro
def pagina_cuenta(user):
    st.header("Cuenta de cobro")
    if user["rol"] == "admin":
        arbs = core.listar_arbitros()
        if not arbs:
            st.info("Aún no hay árbitros. Carga primero un archivo de designaciones.")
            return
        opciones = {a["nombre"]: a["id"] for a in arbs}
        nombre = st.selectbox("Árbitro", list(opciones))
        arbitro_id = opciones[nombre]
    else:
        arbitro_id = user["arbitro_id"]

    torneos = [core.TODOS] + core.listar_torneos()
    rango = core.rango_fechas()
    desde0, hasta0 = rango if rango else (date.today() - timedelta(days=30), date.today())

    n = st.session_state.setdefault("n_filtros", 1)
    filtros = []
    for i in range(n):
        c1, c2, c3 = st.columns([2, 1, 1])
        t = c1.selectbox("Torneo", torneos, key=f"torneo_{i}")
        d = c2.date_input("Desde", desde0, key=f"desde_{i}")
        h = c3.date_input("Hasta", hasta0, key=f"hasta_{i}")
        filtros.append({"torneo": t, "desde": d, "hasta": h})

    b1, b2, b3, _ = st.columns([1.3, 1.3, 1, 3])
    if b1.button("➕ Agregar otro torneo"):
        st.session_state.n_filtros += 1
        st.rerun()
    if n > 1 and b2.button("➖ Quitar el último"):
        st.session_state.n_filtros -= 1
        st.rerun()
    if b3.button("Calcular", type="primary"):
        if any(f["desde"] > f["hasta"] for f in filtros):
            st.error("Una de las fechas «Desde» es posterior a «Hasta».")
        else:
            st.session_state.resultado = (arbitro_id, core.calcular_cuenta(arbitro_id, filtros))

    guardado = st.session_state.get("resultado")
    if not guardado or guardado[0] != arbitro_id:
        return
    res = guardado[1]
    st.divider()
    if not res["filas"]:
        st.warning("No hay servicios en ese rango de fechas y torneo.")
        return

    st.subheader(res["arbitro"])
    df = pd.DataFrame(res["filas"])
    vista = pd.DataFrame({
        "Torneo": df["Torneo"], "Fecha": df["Fecha"].map(core.fecha_bonita), "Categ.": df["Categ."],
        "Cant. As.": df["Cant. As."], "Valor unit. Asistencias": df["Valor unit. Asistencias"].map(core.fmt),
        "Cant. C.": df["Cant. C."], "Valor unit. Centros": df["Valor unit. Centros"].map(core.fmt),
        "Pasaje": df["Pasaje"].map(core.fmt), "Valor Total": df["Valor Total"].map(core.fmt)})
    if df["Cant. E."].any():  # columnas de emergente solo si hubo servicios como emergente
        vista.insert(7, "Cant. E.", df["Cant. E."])
        vista.insert(8, "Valor unit. Emergentes", df["Valor unit. Emergentes"].map(core.fmt))
    if user["rol"] == "admin" and df["Aviso"].any():
        vista["Aviso"] = df["Aviso"]
    st.dataframe(vista, hide_index=True)
    st.metric("Total General", f"$ {core.fmt(res['total'])}")

    if res["sin_precio"] or res["sin_pasaje"] or res["sin_residencia"]:
        st.warning("Hay valores pendientes por configurar, así que este total puede estar incompleto. "
                   "Avisa a un administrador.")
    if user["rol"] == "admin":
        for torneo, cat, rol in res["sin_precio"]:
            st.caption(f"⚠️ Falta precio: {torneo} / {cat} / {rol}")
        for resid, ciudad in res["sin_pasaje"]:
            st.caption(f"⚠️ Falta pasaje: {resid} → {ciudad.title()}")
        if res["sin_residencia"]:
            st.caption("⚠️ Este árbitro no tiene lugar de residencia y el torneo paga pasaje.")
    if res["otros"]:
        st.info("No se cobran (aún no tienen valor definido): "
                + ", ".join(f"{v} como {k}" for k, v in res["otros"].items()))

    st.download_button("⬇️ Descargar en Excel", core.exportar_xlsx(res),
                       f"cuenta_{res['arbitro'].replace(' ', '_')}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------- perfil árbitro
def pagina_perfil(user):
    st.header("Mi perfil")
    arb = next(a for a in core.listar_arbitros() if a["id"] == user["arbitro_id"])
    st.write(f"**{arb['nombre']}**")
    actual = arb["residencia"] if arb["residencia"] in core.RESIDENCIAS else core.RESIDENCIAS[0]
    nueva = st.selectbox("Lugar de residencia", core.RESIDENCIAS, index=core.RESIDENCIAS.index(actual))
    if st.button("Guardar residencia"):
        core.actualizar_residencia(arb["id"], nueva)
        st.success("Guardado.")
    st.divider()
    with st.form("cambio_clave"):
        c1 = st.text_input("Nueva contraseña", type="password")
        if st.form_submit_button("Cambiar contraseña"):
            try:
                core.cambiar_password(user["id"], c1)
                st.success("Contraseña actualizada.")
            except ValueError as e:
                st.error(str(e))


# ------------------------------------------------------------ administración
def pagina_cargar():
    st.header("Cargar designaciones")
    st.caption("Sube el Excel (.xlsx) o CSV de la comisión designadora. Se pueden subir varios a la vez; "
               "los partidos repetidos no se cuentan dos veces.")
    archivos = st.file_uploader("Archivos", type=["xlsx", "csv"], accept_multiple_files=True)
    if archivos and st.button("Procesar archivos", type="primary"):
        for f in archivos:
            st.subheader(f.name)
            try:
                r = core.importar_designaciones(f, f.name)
            except Exception as e:
                st.error(f"No se pudo leer: {e}")
                continue
            c1, c2, c3 = st.columns(3)
            c1.metric("Servicios nuevos", r["nuevos"])
            c2.metric("Ya estaban cargados", r["duplicados"])
            c3.metric("Filas omitidas", len(r["omitidas"]))
            if r["arbitros_nuevos"]:
                st.info(f"Árbitros nuevos ({len(r['arbitros_nuevos'])}): " + ", ".join(r["arbitros_nuevos"]))
            for nuevo, parecido in r["posibles_duplicados"]:
                st.warning(f"«{nuevo}» se parece mucho a «{parecido}». ¿Es la misma persona escrita distinto?")
            if r["omitidas"]:
                st.error("Filas omitidas por datos incompletos (corrígelas en el Excel y vuelve a subirlo):")
                st.dataframe(pd.DataFrame(r["omitidas"], columns=["Fila de Excel", "Motivo"]), hide_index=True)
            if r["roles_raros"]:
                st.warning("Servicios con un rol sin valor definido (no se cobran): "
                           + ", ".join(f"{k}: {v}" for k, v in r["roles_raros"].items()))


def pagina_precios():
    st.header("Precios y pasajes")
    t1, t2, t3, t4 = st.tabs(["Valor por servicio", "Tipo de pasaje por torneo",
                              "Pasaje según residencia", "Pasaje de valor único"])

    with t1:
        df = core.tabla_precios()
        if df.empty:
            st.info("Carga primero designaciones.")
        else:
            faltan = int(df["Valor"].isna().sum())
            st.caption(f"{faltan} combinaciones sin precio." if faltan else "Todos los precios están definidos.")
            ed = st.data_editor(df, hide_index=True, key="ed_precios",
                                disabled=["Torneo", "Categoría", "Rol"],
                                column_config={"Valor": st.column_config.NumberColumn(min_value=0, step=1000)})
            if st.button("Guardar precios", type="primary"):
                core.guardar_precios(ed)
                st.success("Precios guardados.")
                st.rerun()

    with t2:
        st.caption("Para cada torneo elige: no paga pasaje, paga según dónde vive el árbitro, "
                   "o paga un valor único por ciudad del partido sin importar dónde viva.")
        df = core.tabla_torneos()
        ed = st.data_editor(df, hide_index=True, key="ed_torneos", disabled=["Torneo"],
                            column_config={"Pasaje": st.column_config.SelectboxColumn(
                                options=core.MODOS_PASAJE, required=True, width="large")})
        if st.button("Guardar torneos"):
            core.guardar_torneos(ed)
            st.success("Guardado.")

    with t3:
        resid = st.selectbox("Lugar de residencia del árbitro", core.RESIDENCIAS)
        df = core.tabla_pasajes(resid)
        if df.empty:
            st.info("Carga primero designaciones.")
        else:
            ed = st.data_editor(df, hide_index=True, key=f"ed_pasajes_{resid}",
                                disabled=["Ciudad del partido"],
                                column_config={"Pasaje": st.column_config.NumberColumn(min_value=0, step=1000)})
            if st.button("Guardar pasajes"):
                core.guardar_pasajes(resid, ed)
                st.success("Guardado.")

    with t4:
        unicos = core.torneos_pasaje_unico()
        if not unicos:
            st.info("Ningún torneo tiene pasaje de valor único. Actívalo en la pestaña «Tipo de pasaje por torneo».")
        else:
            torneo = st.selectbox("Torneo", unicos)
            df = core.tabla_pasajes_torneo(torneo)
            ed = st.data_editor(df, hide_index=True, key=f"ed_unico_{torneo}", disabled=["Ciudad del partido"],
                                column_config={"Pasaje": st.column_config.NumberColumn(min_value=0, step=1000)})
            if st.button("Guardar pasajes del torneo"):
                core.guardar_pasajes_torneo(torneo, ed)
                st.success("Guardado.")


def pagina_arbitros():
    st.header("Árbitros")
    arbs = core.listar_arbitros()
    df = pd.DataFrame(arbs)
    if not df.empty:
        df["Cuenta"] = df["usuario_id"].notna().map({True: "Sí", False: "Pendiente"})
        df["residencia"] = df["residencia"].fillna("")
        ed = st.data_editor(
            df[["id", "nombre", "residencia", "Cuenta"]].rename(columns={"nombre": "Nombre", "residencia": "Residencia"}),
            hide_index=True, key="ed_arbs", column_order=["Nombre", "Residencia", "Cuenta"],
            disabled=["id", "Nombre", "Cuenta"],
            column_config={"Residencia": st.column_config.SelectboxColumn(options=[""] + core.RESIDENCIAS)})
        if st.button("Guardar residencias"):
            for _, r in ed.iterrows():
                core.actualizar_residencia(int(r["id"]), r["Residencia"])
            st.success("Guardado.")

    with st.expander("Agregar árbitro manualmente"), st.form("nuevo_arbitro", clear_on_submit=True):
        nombre = st.text_input("Nombre completo")
        if st.form_submit_button("Agregar") and nombre.strip():
            try:
                core.agregar_arbitro(nombre)
                st.success("Agregado.")
            except ValueError as e:
                st.error(str(e))

    con_cuenta = {a["nombre"]: a["usuario_id"] for a in arbs if a["usuario_id"]}
    if con_cuenta:
        with st.expander("Restablecer contraseña de un árbitro"), st.form("reset"):
            quien = st.selectbox("Árbitro", list(con_cuenta))
            nueva = st.text_input("Nueva contraseña temporal", type="password")
            if st.form_submit_button("Restablecer"):
                try:
                    core.cambiar_password(con_cuenta[quien], nueva)
                    st.success("Contraseña actualizada.")
                except ValueError as e:
                    st.error(str(e))


# ------------------------------------------------------------------- principal
def main():
    user = st.session_state.user
    if not user:
        return pantalla_ingreso()

    with st.sidebar:
        mostrar_logo(100)
        st.markdown("### Cuentas Coarcun")
        st.write(f"**{user['nombre']}**  \n{'Administrador' if user['rol'] == 'admin' else 'Árbitro'}")
        if user["rol"] == "admin":
            paginas = {"Cuenta de cobro": lambda: pagina_cuenta(user), "Cargar designaciones": pagina_cargar,
                       "Precios y pasajes": pagina_precios, "Árbitros": pagina_arbitros}
        else:
            paginas = {"Mi cuenta de cobro": lambda: pagina_cuenta(user), "Mi perfil": lambda: pagina_perfil(user)}
        eleccion = st.radio("Menú", list(paginas), label_visibility="collapsed")
        if st.button("Cerrar sesión"):
            st.session_state.clear()
            st.rerun()
    paginas[eleccion]()


main()
