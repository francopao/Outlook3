import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import plotly.express as px
import plotly.graph_objects as go
import io
from fredapi import Fred
import fear_and_greed
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import textwrap
from dateutil.relativedelta import relativedelta
import yfinance as yf
from io import StringIO

# --------------------------------------
# SCRAPER Y TRANSFORMADOR DE DATOS
# --------------------------------------
fred = Fred(api_key='762e2ee1c8fab5d038ce317929d47226')

# --------------------------------------
# FUNCION PARA INDICES
def render_equity_table(df, height=420):
    df_display = df.copy()

    # Columnas porcentuales
    cols_pct = ["Latest 7d", "MTD", "YTD", df_display.columns[-1]]
    for col in cols_pct:
        if col in df_display.columns:
            df_display[col] = df_display[col].apply(render_percent)

    # Level formatting
    if "Level" in df_display.columns:
        df_display["Level"] = df_display["Level"].apply(
            lambda x: f"{x:,.2f}" if isinstance(x, (float, int)) and x != 0 else ""
        )

    fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=[f"<b>{v}</b>" for v in df_display.columns],
                    fill_color="#003366",
                    font=dict(color="white", size=14),
                    align="center",
                    height=40
                ),
                cells=dict(
                    values=[df_display[col] for col in df_display.columns],
                    align="center",
                    height=32,
                    font=dict(size=13)
                )
            )
        ]
    )

    fig.update_layout(height=height)
    return fig

# --------------------------------------
# FUNCIONES FRED
# --------------------------------------
    
def obtener_datos_fred():
    codigos = {
        # Labor Market
        "Total Nonfarm Payrolls": "PAYEMS",
        "Unemployment Rate": "UNRATE",
        "Labor Force Participation Rate": "CIVPART",
        "Job Openings (JOLTS)": "JTSJOL",
        "Average Hourly Earnings (Total Private)": "CES0500000003",
        "U-6 Unemployment Rate": "U6RATE",
        "Quits Rate (JOLTS)": "JTSQUR",

        # Credit/Market
        "Rating AAA": "BAMLC0A1CAAA",
        "Rating AA": "BAMLC0A2CAA",
        "Rating A": "BAMLC0A3CA",
        "Rating BBB": "BAMLC0A4CBBB",
        "BBB o superior": "BAMLC0A0CM",
        "High Yield": "BAMLH0A0HYM2EY",
        "Investment Grade": "BAMLC0A4CBBBEY",
        "Rating AAA ": "BAMLC0A1CAAASYTW",
        "Rating AA ": "BAMLC0A2CAASYTW",
        "Rating A ": "BAMLC0A3CASYTW",
        "Rating BBB ": "BAMLC0A4CBBBSYTW",
        "High Yield ": "BAMLH0A0HYM2SYTW",
        "10-Year Treasury Market Yield ": "DGS10",
        "5-Year Inflation Expectation ": "T5YIFR",
        "2-Year Treasury Market Yield ": "DGS2",
        "Rating AAA Corporate Yield ": "BAMLC0A1CAAAEY",
        
        # YTW bonds to economic zone
        "Global": "BAMLEMUBCRPIUSSYTW",
        "Euro": "BAMLEMEBCRPIESYTW",
        "Latin America": "BAMLEMRLCRPILASYTW",
        "Asia": "BAMLEMRACRPIASIASYTW",
        "EMEA": "BAMLEMRECRPIEMEASYTW",
        
        # Michingan Consumer Sentiment Index - MCSI
     #   "MSCI": "UMCSENT",
     #   "Home Purchase Sentiment Index":"HPSI",
        
        # Monetary Policy
        "Inflation Expectation (University of Michigan)": "MICH",
        "CPI":"CPIAUCSL",
        "30-year Breakeven Inflation": "T30YIEM",
        "5-Year Breakeven Inflation":"T5YIE",
        
        # Consumption
       # "Retail Sales": "RSXFS",
       # "S&P National Home Price Index":"CSUSHPINSA",
       # "Personal Consumption Expenditures": "PCE",
       # "Total Vehicle Sales": "TOTALSA"

    }
    datos = {}

    for nombre, codigo in codigos.items():
        serie = fred.get_series(codigo)
        serie.name = nombre
        datos[nombre] = serie
    return datos

def graficar_fred(datos, titulo, series, zoom=False):
    fig = go.Figure()
    for serie in series:
        data = datos[serie].tail(30) if zoom else datos[serie]
        fig.add_trace(go.Scatter(x=data.index, y=data.values, mode='lines', name=serie))
    fig.update_layout(title=titulo, xaxis_title="Fecha", yaxis_title="Valor", template="plotly_white")
    return fig

@st.cache_data
def load_equity_table():
    file_path = "data/indices_globales.xlsx"
    return pd.read_excel(file_path)

def render_percent(val):
    if pd.isna(val) or val == 0:
        return ""

    val_pct = val * 100
    arrow = "▲" if val > 0 else "▼"
    return f"{arrow} {val_pct:.2f}%"
@st.cache_data(show_spinner=False)
def load_benchmarks():

    yahoo_assets = {
        "Global equities": "SPY",
        "GEM equities": "EEM",
        "Global government bonds": "IGLO.L",
        "Global EM government bonds": "LEMB",
        "Gold": "GLD",
        "Other commodities": "^BCOM",
        "Real estate": "REET",
        "Crypto": "BTC-USD"
    }

    fred_series = {
        "Global HY corp bonds": "BAMLH0A0HYM2EY",
        "Global IG corp bonds": "BAMLC0A0CMEY"
    }

    benchmark1 = {}

    for name, ticker in yahoo_assets.items():
        df = yf.download(ticker, progress=False)[["Close"]]
        benchmark1[name] = df.rename(columns={"Close": name})

    for name, series_id in fred_series.items():
        data = fred.get_series(series_id)
        df = pd.DataFrame(data, columns=[name])
        df.index = pd.to_datetime(df.index)
        benchmark1[name] = df

    return benchmark1


def compute_period_returns(benchmark1):
    today = pd.Timestamp.today().normalize()

    last_year = today.year - 1
    start_last_year = pd.Timestamp(f"{last_year}-01-01")
    end_last_year   = pd.Timestamp(f"{last_year}-12-31")
    start_ytd = pd.Timestamp(f"{today.year}-01-01")

    last_month_end   = today.replace(day=1) - pd.Timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    label_last_year  = str(last_year)
    label_ytd        = "YTD"
    label_last_month = last_month_start.strftime("%b%y")

    rows = []

    for category, df in benchmark1.items():
        series = df.iloc[:, 0].dropna()

        try:
            r_last_year = (series.loc[:end_last_year].iloc[-1] /
                           series.loc[:start_last_year].iloc[-1] - 1) * 100
        except:
            r_last_year = None

        try:
            r_ytd = (series.iloc[-1] /
                     series.loc[:start_ytd].iloc[-1] - 1) * 100
        except:
            r_ytd = None

        try:
            r_last_month = (series.iloc[-1] /
                            series.loc[:last_month_start].iloc[-1] - 1) * 100
        except:
            r_last_month = None

        rows.extend([
            [category, label_last_year, r_last_year],
            [category, label_ytd, r_ytd],
            [category, label_last_month, r_last_month],
        ])

    return pd.DataFrame(rows, columns=["Category", "Period", "Value"])


# --- Inputs de imagen de barras (GLOBAL, SIN INDENTACIÓN)
@st.cache_data(show_spinner=False)
def load_asset_class1():
    benchmark1 = load_benchmarks()
    return compute_period_returns(benchmark1)


asset_class1 = load_asset_class1()
    
# ---- Cálculo de rentabilidades ----
def compute_period_returns_alt(benchmark1):

    rows = []

    for category, df in benchmark1.items():

        # La serie se supone que tiene solo 1 columna
        series = df.iloc[:, 0].dropna()

        # --- Rentabilidad año anterior ---
        try:
            price_start = series.loc[:start_last_year].iloc[-1]
            price_end = series.loc[:end_last_year].iloc[-1]
            r_last_year = (price_end / price_start - 1) * 100
        except:
            r_last_year = None

        # --- Rentabilidad YTD ---
        try:
            price_start = series.loc[:start_ytd].iloc[-1]
            price_end = series.iloc[-1]
            r_ytd = (price_end / price_start - 1) * 100
        except:
            r_ytd = None

        # --- Rentabilidad mes pasado completo a hoy ---
        try:
            price_start = series.loc[:last_month_start].iloc[-1]
            price_end = series.iloc[-1]
            r_last_month = (price_end / price_start - 1) * 100
        except:
            r_last_month = None

        # --- Agregar resultados ---
        rows.append([category, label_last_year, r_last_year])
        rows.append([category, label_ytd, r_ytd])
        rows.append([category, label_last_month, r_last_month])

    # ---- DataFrame final (dentro del def, fuera del for) ----
    df_out = pd.DataFrame(rows, columns=["Category", "Period", "Value"])
    return df_out



# --------------------------------------
# STREAMLIT UI
# --------------------------------------

st.set_page_config(layout="wide")
st.image("https://media.licdn.com/dms/image/v2/D4D03AQFPldTT75xHfA/profile-displayphoto-scale_200_200/B4DZsPFlJ2LUAc-/0/1765484680480?e=1768435200&v=beta&t=e_s3qJ-SEoYzKk-5YYe7raLSnmd70XJuIFUGU_j7YoY", 
         width=200)
st.title("Global Fixed Income Dashboard - Franco Olivares")

tab1, tab2, tab3, tab4 = st.tabs(["Treasury Yields", "US Corporate Bonds", "US Labor Market", "Equity"])

# --------------------------------------
# TAB 1: CURVAS DEL TESORO
# --------------------------------------
with tab1:

    st.image(
        "https://images.pexels.com/photos/12422182/pexels-photo-12422182.jpeg",
        use_container_width=True
    )

    st.markdown("### Treasury Yield Curves")

    # -------------------------------
    # CARGA DIRECTA DEL EXCEL
    # -------------------------------
    df = pd.read_excel("data/df_tesoro.xlsx")

    # Limpieza mínima pero CLAVE
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    # Selector de años (últimos 3 por defecto)
    años_disponibles = sorted(df["Year"].unique())
    años = st.multiselect(
        "Selecciona año(s):",
        años_disponibles,
        default=años_disponibles[-1:]
    )

    df = df[df["Year"].isin(años)]

    # -------------------------------
    # VALIDACIÓN
    # -------------------------------
    if not df.empty:
        st.success(f"{df.shape[0]} registros obtenidos.")

        # ===============================
        # FECHAS
        # ===============================
        fechas = sorted(df["Date"].unique())
        fechas_seleccionadas = st.multiselect(
            "Selecciona una o más fechas para comparar curvas:",
            fechas[-10:],
            default=fechas[-3:]
        )

        # ===============================
        # SPREAD 10Y - 2Y
        # ===============================
        if {"10 Yr", "2 Yr"}.issubset(df.columns):
            df["Spread 10Y - 2Y"] = df["10 Yr"] - df["2 Yr"]
            st.metric(
                "📉 Spread 10Y - 2Y actual",
                f"{df['Spread 10Y - 2Y'].iloc[-1]:.2f} %"
            )

            fig_spread = px.line(
                df, x="Date", y="Spread 10Y - 2Y",
                title="Evolución del Spread 10Y - 2Y"
            )
            st.plotly_chart(fig_spread, use_container_width=True)

        # ===============================
        # CURVAS POR FECHA
        # ===============================
        st.subheader("Comparación de curvas por fecha")
        fig_comparacion = px.line()

        maturities = [
            col for col in df.columns
            if col not in ["Date", "Year", "Spread 10Y - 2Y"]
        ]

        for fecha in fechas_seleccionadas:
            fila = df[df["Date"] == fecha].iloc[0]
            tasas = fila[maturities].astype(float).values

            fig_comparacion.add_scatter(
                x=maturities,
                y=tasas,
                mode="lines+markers",
                name=fecha.strftime("%Y-%m-%d")
            )

        fig_comparacion.update_layout(
            title="Curvas de rendimiento comparadas",
            xaxis_title="Plazo",
            yaxis_title="Rendimiento (%)"
        )
        st.plotly_chart(fig_comparacion, use_container_width=True)

        # ===============================
        # ANIMACIÓN
        # ===============================
        st.subheader("Rendimiento de los bonos del Tesoro a la par")

        df_anim = df.melt(
            id_vars=["Date"],
            value_vars=maturities,
            var_name="Maturity",
            value_name="Yield"
        )

        fig_anim = px.line(
            df_anim,
            x="Maturity",
            y="Yield",
            animation_frame=df_anim["Date"].dt.strftime("%Y-%m-%d"),
            title="Evolución diaria de la curva de rendimiento"
        )
        fig_anim.update_layout(
            xaxis_title="Plazo",
            yaxis_title="Rendimiento (%)"
        )
        st.plotly_chart(fig_anim, use_container_width=True)

        # ===============================
        # EXPORTAR
        # ===============================
        st.subheader("Exportar datos")

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Yield Curve")
            if "Spread 10Y - 2Y" in df.columns:
                df[["Date", "Spread 10Y - 2Y"]].to_excel(
                    writer, index=False, sheet_name="Spread"
                )

        st.download_button(
            label="⬇️ Descargar Excel",
            data=output.getvalue(),
            file_name="treasury_yield_curve.xlsx"
        )

    else:
        st.warning("No se encontraron datos para los años seleccionados.")

# Fixed Income 
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fredapi import Fred
from datetime import datetime  # <--- Homogenizado aquí

# --- Dentro de tu bloque de pestañas ---
with tab2:
    st.header("Análisis de Tasas y Expectativas de Inflación (FRED)")
    
    # 1) Conexión y Configuración
    api_key = "762e2ee1c8fab5d038ce317929d47226"
    fred = Fred(api_key=api_key)
    start_date = "2021-01-01"

    # Uso de spinner para feedback visual
    with st.spinner("Descargando datos macroeconómicos de la FRED..."):
        try:
            # Descarga de series directamente
            dgs10  = fred.get_series('DGS10',  observation_start=start_date)  # Nominal 10Y
            dfii10 = fred.get_series('DFII10', observation_start=start_date)  # Real 10Y (TIPS)
            t10yie = fred.get_series('T10YIE', observation_start=start_date)  # Breakeven 10Y
            effr   = fred.get_series('EFFR',   observation_start=start_date)  # Fed Funds Rate

            # Unir en DataFrame y limpiar
            df_macro = pd.concat([dgs10, dfii10, t10yie, effr], axis=1)
            df_macro.columns = ['DGS10', 'DFII10', 'T10YIE', 'EFFR']
            df_macro = df_macro.dropna()

            # 2) Construcción del gráfico Plotly
            fig_macro = go.Figure()

            # Serie Nominal 10Y
            fig_macro.add_trace(go.Scatter(
                x=df_macro.index, y=df_macro['DGS10'],
                mode='lines', name='Nominal 10Y (DGS10)',
                line=dict(color='blue', width=2)
            ))

            # Serie Breakeven 10Y
            fig_macro.add_trace(go.Scatter(
                x=df_macro.index, y=df_macro['T10YIE'],
                mode='lines', name='Breakeven 10Y (T10YIE)',
                line=dict(color='orange', width=2)
            ))

            # Serie Real 10Y (Sombreado)
            fig_macro.add_trace(go.Scatter(
                x=df_macro.index, y=df_macro['DFII10'],
                mode='lines', name='Real 10Y (DFII10)',
                line=dict(color='gray', width=1, dash='dot'),
                fill='tozeroy', fillcolor='rgba(128, 128, 128, 0.15)'
            ))

            # Serie Fed Funds Rate (Eje Y Secundario)
            fig_macro.add_trace(go.Scatter(
                x=df_macro.index, y=df_macro['EFFR'],
                mode='lines', name='Fed Funds Rate (EFFR)',
                line=dict(color='#B91C1C', width=1, dash='dash'),
                opacity=0.8, yaxis='y2'
            ))

            # 3) Marcadores de Eventos
            # Ajustado: Usamos datetime() directamente porque importamos la clase
            events = [
                (datetime(2022, 3, 16), "Fed hike Mar 2022"),
                (datetime(2022, 6, 13), "US CPI peak Jun 2022"),
                (datetime(2022, 2, 24), "War in Ukraine Feb 2022")
            ]

            for ev_date, label in events:
                # Buscar la fecha más cercana en el índice para posicionar el punto
                idx_pos = df_macro.index.searchsorted(ev_date)
                if idx_pos < len(df_macro.index):
                    actual_date = df_macro.index[idx_pos]
                    fig_macro.add_trace(go.Scatter(
                        x=[actual_date],
                        y=[df_macro.loc[actual_date, 'DGS10']],
                        mode='markers',
                        marker=dict(color='red', size=10, symbol='circle'),
                        text=[label],
                        hoverinfo="text",
                        showlegend=False
                    ))

            # 4) Layout Profesional
            fig_macro.update_layout(
                title="Nominal vs Breakeven vs Real Yield (10Y)",
                xaxis_title="Fecha",
                yaxis_title="Yield (%)",
                hovermode="x unified",
                template="plotly_white",
                height=600,
                legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center"),
                yaxis2=dict(
                    title="Fed Funds Rate (%)",
                    overlaying='y',
                    side='right',
                    showgrid=False
                )
            )

            # Renderizar gráfico
            st.plotly_chart(fig_macro, use_container_width=True)

            # 5) Resumen de valores actuales
            st.subheader("Valores de Cierre Actuales")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Nominal 10Y", f"{df_macro['DGS10'].iloc[-1]:.2f}%")
            c2.metric("Real 10Y", f"{df_macro['DFII10'].iloc[-1]:.2f}%")
            c3.metric("Breakeven 10Y", f"{df_macro['T10YIE'].iloc[-1]:.2f}%")
            c4.metric("Fed Funds", f"{df_macro['EFFR'].iloc[-1]:.2f}%")

        except Exception as e:
            st.error(f"Error al procesar los datos de FRED: {e}")

    start_date = "2021-01-01"

    with st.spinner("Descargando rendimientos corporativos..."):
        try:
            # Diccionario para mantener el orden de la leyenda solicitado
            series_dict = {
                'BAMLC0A1CAAAEY': 'AAA',
                'BAMLC0A2CAAEY': 'AA',
                'BAMLC0A3CAEY': 'A',
                'BAMLC0A4CBBBEY': 'BBB',
                'BAMLH0A1HYBBEY': 'BB',
                'BAMLH0A2HYBEY': 'B',
                'BAMLH0A3HYCEY': 'CCC'
            }

            # Descarga de series corporativas
            data_list = []
            for id_serie, nombre in series_dict.items():
                s = fred.get_series(id_serie, observation_start=start_date)
                s.name = nombre
                data_list.append(s)
            
            # Descarga del DGS10 (Benchmark)
            dgs10 = fred.get_series('DGS10', observation_start=start_date)
            dgs10.name = 'DGS10'
            data_list.append(dgs10)

            # Unir y limpiar
            df_credit = pd.concat(data_list, axis=1)
            df_credit = df_credit.dropna()

            # 2) Construcción del gráfico Plotly
            fig_credit = go.Figure()

            # --- DGS10: Área sombreada sin líneas (Fondo) ---
            fig_credit.add_trace(go.Scatter(
                x=df_credit.index, 
                y=df_credit['DGS10'],
                mode='lines',
                line=dict(width=0), # Sin línea
                fill='tozeroy',
                fillcolor='rgba(200, 200, 200, 0.3)', # Gris suave
                name='Treasury 10Y (DGS10)',
                hoverinfo='skip' # No distrae en el hover
            ))

            # --- Series Corporativas (Líneas protagonistas) ---
            # Colores en escala de riesgo (de azul frío a rojo caliente)
            colors = {
                'AAA': '#1E3A8A', 'AA': '#2563EB', 'A': '#60A5FA', 
                'BBB': '#F59E0B', 'BB': '#EA580C', 'B': '#DC2626', 'CCC': '#7F1D1D'
            }

            for rating in series_dict.values():
                fig_credit.add_trace(go.Scatter(
                    x=df_credit.index,
                    y=df_credit[rating],
                    mode='lines',
                    name=rating,
                    line=dict(color=colors.get(rating), width=2)
                ))

            # 3) Layout Profesional
            fig_credit.update_layout(
                title="Corporate Bond Yields by Credit Rating vs Treasury 10Y",
                xaxis_title="Fecha",
                yaxis_title="Yield (%)",
                hovermode="x unified",
                template="plotly_white",
                height=650,
                legend=dict(
                    orientation="h", 
                    y=-0.15, 
                    x=0.5, 
                    xanchor="center",
                    traceorder="normal" # Mantiene el orden en que fueron añadidos
                ),
                margin=dict(l=20, r=20, t=60, b=100)
            )

            # Renderizar gráfico
            st.plotly_chart(fig_credit, use_container_width=True)

            # 4) Métricas Rápidas (Último valor)
            st.subheader("Current Yields (Latest)")
            cols = st.columns(len(series_dict))
            for i, rating in enumerate(series_dict.values()):
                cols[i].metric(rating, f"{df_credit[rating].iloc[-1]:.2f}%")

        except Exception as e:
            st.error(f"Error al procesar datos de crédito: {e}")

# --- Nuevo Bloque: Activos y Pasivos por Distrito FED ---
# --- Nuevo Bloque: Activos y Pasivos por Distrito FED ---
st.markdown("---")
st.subheader("FED Assets & Liabilities by District")

with st.spinner("Descargando balances de distritos FED..."):
    try:
        # Definición de distritos y sus respectivas series FRED
        distritos = [
            "Boston", "New York", "Philadelphia", "Cleveland", 
            "Richmond", "Atlanta", "Chicago", "St. Louis", 
            "Minneapolis", "Kansas City", "Dallas", "San Francisco"
        ]
        
        assets_series = [f"D{i}WATAL" for i in range(1, 13)]
        liab_series = [f"D{i}WLTOTL" for i in range(1, 13)]

        assets_data = []
        liab_data = []

        for a_id, l_id in zip(assets_series, liab_series):
            # Obtenemos el último dato y aseguramos que sea float
            a_val = fred.get_series(a_id).iloc[-1]
            l_val = fred.get_series(l_id).iloc[-1]
            assets_data.append(a_val)
            liab_data.append(l_val)

        # Crear DataFrame
        df_fed = pd.DataFrame({
            'Distrito': distritos,
            'Assets': assets_data,
            'Liabilities': liab_data
        })

        # SOLUCIÓN AL ERROR: Convertir columnas a numérico explícitamente
        df_fed['Assets'] = pd.to_numeric(df_fed['Assets'], errors='coerce')
        df_fed['Liabilities'] = pd.to_numeric(df_fed['Liabilities'], errors='coerce')
        df_fed = df_fed.fillna(0) # Reemplazar nulos por 0 para que no falle el formato

        # Construcción del gráfico
        fig_fed = go.Figure()

        fig_fed.add_trace(go.Bar(
            y=df_fed['Distrito'],
            x=df_fed['Assets'],
            name='Assets',
            orientation='h',
            marker=dict(color='#1E3A8A')
        ))

        fig_fed.add_trace(go.Bar(
            y=df_fed['Distrito'],
            x=df_fed['Liabilities'],
            name='Liabilities',
            orientation='h',
            marker=dict(color='#DC2626')
        ))

        fig_fed.update_layout(
            title="Federal Reserve Banks: Total Assets vs Liabilities by District",
            xaxis_title="Millions of US Dollars",
            yaxis=dict(autorange="reversed"),
            barmode='group',
            template="plotly_white",
            height=700,
            hovermode="y unified",
            legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center")
        )

        st.plotly_chart(fig_fed, use_container_width=True)

        # Mostrar tabla resumen con el formato corregido
        with st.expander("Ver tabla de datos (Millones USD)"):
            # Aplicamos el formato solo a las columnas numéricas
            st.dataframe(df_fed.style.format({
                'Assets': '{:,.2f}',
                'Liabilities': '{:,.2f}'
            }))

    except Exception as e:
        st.error(f"Error al cargar los balances de la FED: {e}")



    st.markdown("---")
    st.subheader("FED H.4.1: Factors Affecting Reserve Balances")


    # 1) Mapeo Exacto de Series
    assets_map = {
        "Total Assets": "WALCL",
        "Gold certificate account": "WGCAL",
        "Special drawing rights certificate account": "WOSDRL",
        "Coin": "WACL",
        "Bills": "WSHOBL",
        "Notes and bonds, nominal": "WSHONBNL",
        "Notes and bonds, inflation-indexed": "WSHONBIIL",
        "Inflation compensation": "WSHOICL",
        "Federal agency debt securities": "WSHOFADSL",
        "Mortgage-backed securities": "WSHOMCB",
        "Unamortized premiums on securities held outright": "WUPSHO",
        "Unamortized discounts on securities held outright": "WUDSHO",
        "Repurchase agreements": "WORAL",
        "Loans": "WLCFLL",
        "Net portfolio holdings of MS Facilities LLC": "H41RESPPAAENWW",
        "Items in process of collection": "WPCLC",
        "Bank premises": "SWPT",
        "Central bank liquidity swaps": "WABPL",
        "Foreign currency denominated assets": "WFCDA",
        "Other Assets": "WAOAL"
    }

    liabilities_map = {
        "Total Liabilities": "WLTLECL",
        "Federal Reserve Notes, net of F.R. Bank holdings": "WLFN",
        "Reverse repurchase agreements": "WLRRAL",
        "Deposits": "WLDLCL",
        "Treasury contributions to credit facilities": "H41RESH4ENWW",
        "Deferred availability cash items": "WLDACLC",
        "Other Liabilities and Accrued Dividends": "WLAD"
    }

    @st.cache_data(ttl=3600)
    def get_fed_balance_data():
        all_ids = list(assets_map.values()) + list(liabilities_map.values())
        data_frames = []
        for s_id in all_ids:
            try:
                s = fred.get_series(s_id, observation_start='2008-01-01')
                s.name = s_id
                data_frames.append(s)
            except: continue
        return pd.concat(data_frames, axis=1).ffill()

    try:
        df_raw = get_fed_balance_data()
        
        # Referencias Temporales sin usar timedelta
        # Para frecuencia semanal, 'Year Ago' son aproximadamente 52 periodos atrás
        idx_last = -1
        idx_prev = -2
        idx_ya = -53 # 52 semanas en un año + 1 para cuadrar la misma semana
        
        # Hitos específicos usando pd.Timestamp (nativo de pandas, no requiere timedelta)
        m20_dt = pd.Timestamp('2020-03-25')
        m20_prev = pd.Timestamp('2020-03-18')
        o08_dt = pd.Timestamp('2008-10-08')
        o08_prev = pd.Timestamp('2008-10-01')

        def build_rows(mapping, total_id):
            total_val = df_raw[total_id].iloc[idx_last]
            rows = []
            for name, s_id in mapping.items():
                if s_id not in df_raw.columns: continue
                
                # Valores nominales
                val = df_raw[s_id].iloc[idx_last]
                val_prev = df_raw[s_id].iloc[idx_prev]
                
                # Manejo de Year Ago por posición de índice para evitar timedelta
                try:
                    val_ya = df_raw[s_id].iloc[idx_ya]
                except IndexError:
                    val_ya = df_raw[s_id].iloc[0]
                
                # Variaciones
                v_1w = ((val / val_prev) - 1) * 100 if val_prev != 0 else 0
                v_ya = ((val / val_ya) - 1) * 100 if val_ya != 0 else 0
                
                # Hitos históricos
                try:
                    v_m20 = ((df_raw[s_id].asof(m20_dt) / df_raw[s_id].asof(m20_prev)) - 1) * 100
                except: v_m20 = 0
                try:
                    v_o08 = ((df_raw[s_id].asof(o08_dt) / df_raw[s_id].asof(o08_prev)) - 1) * 100
                except: v_o08 = 0

                rows.append({
                    "Fed Account": name,
                    "Last Value": val,
                    "Weight (%)": (val / total_val) * 100,
                    "Var% 1 Week": v_1w,
                    "Year Ago": v_ya,
                    "March 2020": v_m20,
                    "October 2008": v_o08
                })
            return rows

        all_data = build_rows(assets_map, "WALCL") + build_rows(liabilities_map, "WLTLECL")
        df_final = pd.DataFrame(all_data)

        # Estilo visual
        def color_map(v):
            if isinstance(v, (int, float)):
                return f'color: {"#00A86B" if v > 0 else "#DE3163" if v < 0 else "gray"}; font-weight: bold'
            return ''

        st.dataframe(
            df_final.style.format({
                "Last Value": "{:,.0f}",
                "Weight (%)": "{:.2f}%",
                "Var% 1 Week": "{:+.2f}%",
                "Year Ago": "{:+.2f}%",
                "March 2020": "{:+.2f}%",
                "October 2008": "{:+.2f}%"
            }).map(color_map, subset=["Var% 1 Week", "Year Ago", "March 2020", "October 2008"]),
            use_container_width=True,
            height=850
        )

    except Exception as e:
        st.error(f"Error en la tabla: {e}")




    st.markdown("---")
    st.subheader("Sovereign Credit Ratings (S&P Global)")

    @st.cache_data(ttl=86400) 
    def get_sovereign_ratings():
        url = "https://tradingeconomics.com/country-list/rating"
        response = requests.get(url, headers={"User-Agent":"Mozilla/5.0"})
        soup = BeautifulSoup(response.text, "lxml")
        tabla = soup.find("table", {"id":"ctl00_ContentPlaceHolder1_ctl01_GridView1"})
        
        if tabla:
            df = pd.read_html(str(tabla))[0]
            df = df.rename(columns={df.columns[0]: "Country"})
            # Seleccionamos Country, S&P y Equivalencia
            df = df.iloc[:, [0, 1, -1]] 
            df.columns = ["Country", "S&P", "Equivalencia"]
            df["Equivalencia"] = pd.to_numeric(df["Equivalencia"], errors='coerce')
            df = df.dropna(subset=["Equivalencia"])
            return df
        return None

    with st.spinner("Obteniendo calificaciones crediticias..."):
        df_rating = get_sovereign_ratings()

    if df_rating is not None:
        paises_extra = [
            "Peru", "Colombia", "Chile", "Mexico", "Brazil", 
            "United States", "France", "China", "Japan", 
            "Italy", "Germany", "United Kingdom"
        ]
        
        df_top15 = df_rating.nlargest(15, "Equivalencia")
        df_extras = df_rating[df_rating["Country"].isin(paises_extra)]
        df_plot = pd.concat([df_top15, df_extras]).drop_duplicates(subset=["Country"])
        df_plot = df_plot.sort_values("Equivalencia", ascending=True)

        fig_rating = go.Figure()

        fig_rating.add_trace(go.Bar(
            y=df_plot["Country"],
            x=df_plot["Equivalencia"],
            orientation='h',
            text=df_plot["S&P"], # Mantiene la etiqueta S&P dentro o junto a la barra
            textposition='auto',
            marker=dict(
                color=df_plot["Equivalencia"],
                colorscale='RdYlGn', 
                showscale=False
            ),
            hovertemplate="<b>%{y}</b><br>Rating: %{text}<extra></extra>"
        ))

        fig_rating.update_layout(
            title="S&P Global Sovereign Ratings",
            xaxis=dict(
                title="",             # Eliminamos el título del eje X
                showgrid=False,       # Opcional: limpiar cuadrícula para estética minimalista
                showticklabels=False, # ESTA ES LA CLAVE: oculta las etiquetas del eje X
                zeroline=False
            ),
            yaxis=dict(title=""),
            height=700,
            template="plotly_white",
            margin=dict(l=150) 
        )

        st.plotly_chart(fig_rating, use_container_width=True)
        
    else:
        st.error("No se pudo conectar con la fuente de datos.")






with tab3:
    st.subheader("Labor Market: Initial vs. Continued Claims")
    
    api_key = "762e2ee1c8fab5d038ce317929d47226"
    fred = Fred(api_key=api_key)

    @st.cache_data(ttl=3600)
    def get_claims_data():
        # ICSA: Initial Claims (Semanal)
        # CCSA: Continued Claims (Semanal)
        icsa = fred.get_series('ICSA', observation_start='2019-01-01')
        ccsa = fred.get_series('CCSA', observation_start='2019-01-01')
        
        df = pd.DataFrame({'Initial Claims': icsa, 'Continued Claims': ccsa})
        return df.ffill()

    try:
        df_claims = get_claims_data()

        # Crear figura con eje secundario
        fig_claims = go.Figure()

        # Línea para Continued Claims (Eje Principal - Izquierda)
        fig_claims.add_trace(go.Scatter(
            x=df_claims.index,
            y=df_claims['Continued Claims'],
            name="Continued Claims (CCSA)",
            line=dict(color='#1f77b4', width=2),
            fill='tozeroy', # Relleno para dar sensación de volumen
            fillcolor='rgba(31, 119, 180, 0.1)'
        ))

        # Línea para Initial Claims (Eje Secundario - Derecha)
        fig_claims.add_trace(go.Scatter(
            x=df_claims.index,
            y=df_claims['Initial Claims'],
            name="Initial Claims (ICSA)",
            line=dict(color='#d62728', width=2.5),
            yaxis="y2"
        ))

        # Configuración del Layout
        fig_claims.update_layout(
            title="US Weekly Jobless Claims: Initial vs Continued",
            hovermode="x unified",
            template="plotly_white",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(title="Date"),
            yaxis=dict(
                title="Continued Claims (Millions)",
                titlefont=dict(color="#1f77b4"),
                tickfont=dict(color="#1f77b4")
            ),
            yaxis2=dict(
                title="Initial Claims (Thousands)",
                titlefont=dict(color="#d62728"),
                tickfont=dict(color="#d62728"),
                anchor="x",
                overlaying="y",
                side="right"
            ),
            height=600
        )

        st.plotly_chart(fig_claims, use_container_width=True)

        # Métricas rápidas debajo del gráfico
        last_icsa = df_claims['Initial Claims'].iloc[-1]
        last_ccsa = df_claims['Continued Claims'].iloc[-1]
        prev_icsa = df_claims['Initial Claims'].iloc[-2]
        
        col1, col2 = st.columns(2)
        col1.metric("Latest Initial Claims", f"{last_icsa:,.0f}", f"{last_icsa - prev_icsa:,.0f}")
        col2.metric("Latest Continued Claims", f"{last_ccsa:,.0f}")

    except Exception as e:
        st.error(f"Error al cargar datos de Claims: {e}")


    st.markdown("---")
    st.subheader("Labor Market: Unemployment Rate by Ethnicity")
    
    api_key = "762e2ee1c8fab5d038ce317929d47226"
    fred = Fred(api_key=api_key)

    @st.cache_data(ttl=3600)
    def get_unemployment_data():
        # Mapeo de series solicitadas
        series_map = {
            'LNS14000000': 'Total',
            'LNS14000009': 'Latino',
            'LNS14000003': 'White',
            'LNS14032183': 'Asian',
            'LNS14000006': 'Black'
        }
        
        df_list = []
        for s_id, label in series_map.items():
            s = fred.get_series(s_id, observation_start='2005-01-01')
            s.name = label
            df_list.append(s)
            
        return pd.concat(df_list, axis=1).ffill()

    try:
        df_unemp = get_unemployment_data()

        fig_unemp = go.Figure()

        # Colores específicos para cada grupo
        colors = {
            'Total': 'black',
            'Black': '#d62728', # Rojo (históricamente más alta)
            'Latino': '#ff7f0e', # Naranja
            'Asian': '#2ca02c', # Verde (históricamente más baja)
            'White': '#1f77b4'  # Azul
        }

        for col in df_unemp.columns:
            is_total = (col == 'Total')
            fig_unemp.add_trace(go.Scatter(
                x=df_unemp.index,
                y=df_unemp[col],
                name=col,
                line=dict(
                    color=colors.get(col, 'gray'),
                    width=4 if is_total else 2, # Resaltar la tasa total
                    dash='dash' if is_total else 'solid'
                ),
                hovertemplate=f"<b>{col}</b>: %{{y:.1f}}%<extra></extra>"
            ))

        # Configuración del Layout
        fig_unemp.update_layout(
            title="Unemployment Rate: Racial and Ethnic Disparities",
            xaxis_title="Year",
            yaxis_title="Unemployment Rate (%)",
            hovermode="x unified",
            template="plotly_white",
            height=600,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
            yaxis=dict(ticksuffix="%")
        )

        # Añadir sombreado para las recesiones (Opcional pero recomendado)
        # Recesión 2008 y 2020
        recessions = [
            ('2007-12-01', '2009-06-01'),
            ('2020-02-01', '2020-04-01')
        ]
        for start, end in recessions:
            fig_unemp.add_vrect(
                x0=start, x1=end, 
                fillcolor="gray", opacity=0.1, 
                layer="below", line_width=0
            )

        st.plotly_chart(fig_unemp, use_container_width=True)

        # Resumen informativo
        latest_data = df_unemp.iloc[-1].sort_values(ascending=False)
        st.info(f"**Current Status:** The highest unemployment rate is among **{latest_data.index[0]}** ({latest_data.iloc[0]}%), while the lowest is among **{latest_data.index[-1]}** ({latest_data.iloc[-1]}%).")

    except Exception as e:
        st.error(f"Error al cargar datos de desempleo: {e}")






with tab4:
    st.subheader("📊 Equity & Index Performance")

    # 1) Cargar datos
    tabla = load_equity_table()

    # ----------------------------
    # 2) Índices globales
    # ----------------------------
    indices_a_mover = [
        'MSCI Asia',
        'MSCI EM LATAM',
        'MSCI EM',
        'MSCI Europe',
        'MSCI USA'
    ]

    tabla_global = tabla[tabla['Index'].isin(indices_a_mover)].copy()
    tabla = tabla[~tabla['Index'].isin(indices_a_mover)].copy()

    # ----------------------------
    # 3) Índices sectoriales
    # ----------------------------
    indices_sectoriales = [
        "NASDAQ-100 (Tech)",
        "S&P500 Aerospace & Defense",
        "Tecnología (XLK)",
        "Salud",
        "Finanzas",
        "Energía",
        "Consumo Discrecional",
        "Industriales",
        "Materiales",
        "Servicios de Comunicación",
        "Consumo Básico",
        "Bienes Raíces",
        "Servicios Públicos"
    ]

    tabla_sectorial = tabla[tabla["Index"].isin(indices_sectoriales)].copy()
    tabla_residual = tabla[~tabla['Index'].isin(indices_sectoriales)].copy()
    # Ordenar segun YTD return
    tabla_global = tabla_global.sort_values("YTD", ascending=False)
    tabla_sectorial = tabla_sectorial.sort_values("YTD", ascending=False)
    tabla_residual = tabla_residual.sort_values("YTD", ascending=False)

    # ----------------------------
    # 4) Render de tablas
    # ----------------------------
    st.markdown("### Global Equity Indices")
    st.plotly_chart(
        render_equity_table(tabla_global, height=360),
        use_container_width=True
    )

    st.markdown("### Sector Indices")
    st.plotly_chart(
        render_equity_table(tabla_sectorial, height=520),
        use_container_width=True
    )

    st.markdown("### Other Indices")
    st.plotly_chart(
        render_equity_table(tabla_residual, height=420),
        use_container_width=True
    )



    st.markdown("### Risk–Return & Efficient Frontier")

    # Selector de periodo
    try:
        current_date = datetime.datetime.now()
    except AttributeError:
        # ai usas "from datetime import datetime"
        current_date = datetime.now()
    current_year = current_date.year
    prev_year = current_year - 1
    
    periodo = st.selectbox(
        "Selecciona periodo:",
        ["YTD", str(prev_year)]
    )
    
    # Cargar data
    file_path = (
        "data/volatilidad1.xlsx" if periodo == "YTD"
        else "data/volatilidad2.xlsx"
    )
    
    df_vol = pd.read_excel(file_path)
    
    # Sectores permitidos
    indices_validos = [
        "Salud", "S&P500 Aerospace & Defense", "Finanzas", "Energía",
        "Consumo Discrecional", "Industriales", "Materiales",
        "Servicios de Comunicación", "Consumo Básico",
        "Bienes Raíces", "Servicios Públicos", "NASDAQ-100 (Tech)"
    ]
    
    df_vol = df_vol[df_vol["Index"].isin(indices_validos)].copy()
    
    # -------------------------------
    # Frontera eficiente (envolvente)
    # -------------------------------
    df_vol = df_vol.sort_values("Volatility")
    frontier = []
    
    max_ret = -np.inf
    for _, row in df_vol.iterrows():
        if row["Return"] > max_ret:
            frontier.append(row)
            max_ret = row["Return"]
    
    df_frontier = pd.DataFrame(frontier)
    

    # -------------------------------
    # Gráfico
    # -------------------------------
    fig = go.Figure()
    
    # Puntos
    fig.add_trace(go.Scatter(
        x=df_vol["Return"],
        y=df_vol["Volatility"],
        mode="markers+text",
        text=df_vol["Index"],
        textposition="top center",
        name="Assets"
    ))
    
    # Frontera eficiente
    fig.add_trace(go.Scatter(
        x=df_frontier["Return"],
        y=df_frontier["Volatility"],
        mode="lines",
        name="Efficient Frontier"
    ))
    
    fig.update_layout(
        title=f"Risk–Return Profile ({periodo})",
        xaxis_title="Return",
        yaxis_title="Volatility",
        template="plotly_white",
        height=520,
        xaxis=dict(tickformat=".2%"),
        yaxis=dict(tickformat=".2%"))
    
    
    st.plotly_chart(fig, use_container_width=True)

    st.header("Análisis de Activos Globales")
        
    api_key = "762e2ee1c8fab5d038ce317929d47226"
    fred = Fred(api_key=api_key)

    yahoo_assets = {
        "Global equities": "SPY",
        "GEM equities": "EEM",
        "Global government bonds": "IGLO.L",
        "Global EM government bonds": "LEMB",
        "Gold": "GOLD",
        "Other commodities": "^BCOM",
        "Real estate": "REET",
        "Crypto": "BTC-USD"
    }

    fred_series = {
        "Global HY corp bonds": "BAMLH0A0HYM2EY",
        "Global IG corp bonds": "BAMLC0A0CMEY"
    }

    # --- DESCARGA DE DATOS CORREGIDA ---
    @st.cache_data(ttl=3600) # Caché para no descargar cada vez que muevas algo
    def get_all_data():
        data_dict = {}
        
        # Yahoo Finance
        for name, ticker in yahoo_assets.items():
            try:
                # auto_adjust=True y flat_header evitan problemas de formato
                df = yf.download(ticker, progress=False, period="max")
                if not df.empty:
                    # Forzamos a que sea una serie simple de precios de cierre
                    # Usamos .iloc[:, 0] por si yfinance devuelve MultiIndex
                    series = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
                    data_dict[name] = pd.DataFrame(series).rename(columns={series.name: name})
            except Exception as e:
                st.warning(f"Error con {name}: {e}")

        # FRED
        for name, series_id in fred_series.items():
            try:
                s = fred.get_series(series_id)
                data_dict[name] = pd.DataFrame(s, columns=[name])
            except:
                pass
        return data_dict

    benchmark1 = get_all_data()

    # --- LÓGICA DE CÁLCULO ---
    def compute_period_returns(data):
        today = pd.Timestamp.today().normalize()
        # Ajuste para pruebas: si hoy es lunes y no hay datos, usar último dato disponible
        
        last_year = today.year - 1
        start_ly, end_ly = pd.Timestamp(f"{last_year}-01-01"), pd.Timestamp(f"{last_year}-12-31")
        start_ytd = pd.Timestamp(f"{today.year}-01-01")
        last_month_start = (today.replace(day=1) - pd.Timedelta(days=1)).replace(day=1)

        rows = []
        for category, df in data.items():
            series = df.iloc[:, 0].dropna()
            if series.empty: continue

            # Función auxiliar para obtener precio más cercano anterior o igual a la fecha
            def get_price(date):
                idx = series.index.asof(date)
                return series.loc[idx] if pd.notnull(idx) else None

            try:
                # Retorno Año Anterior
                p0_ly, p1_ly = get_price(start_ly), get_price(end_ly)
                r_ly = (p1_ly / p0_ly - 1) * 100 if p0_ly and p1_ly else None
                
                # Retorno YTD
                p0_ytd, p1_now = get_price(start_ytd), series.iloc[-1]
                r_ytd = (p1_now / p0_ytd - 1) * 100 if p0_ytd else None

                # Retorno Mes Pasado
                p0_lm, p1_now2 = get_price(last_month_start), series.iloc[-1]
                r_lm = (p1_now2 / p0_lm - 1) * 100 if p0_lm else None

                rows.append([category, str(last_year), r_ly])
                rows.append([category, "YTD", r_ytd])
                rows.append([category, last_month_start.strftime("%b%y"), r_lm])
            except:
                continue
        return pd.DataFrame(rows, columns=["Category", "Period", "Value"])

    asset_class1 = compute_period_returns(benchmark1)

    # --- GRÁFICO ---
    if not asset_class1.empty:
        # Ordenar periodos: Año pasado, YTD, Mes actual
        periods_order = sorted(asset_class1["Period"].unique(), key=lambda x: ("YTD" in x, x.isdigit()))
        color_map = {periods_order[0]: "black", "YTD": "gray", periods_order[-1]: "red"}

        fig, ax = plt.subplots(figsize=(14, 6))
        categories = asset_class1["Category"].unique()
        x = np.arange(len(categories))
        width = 0.25

        for i, p in enumerate(periods_order):
            subset = asset_class1[asset_class1["Period"] == p]
            # Asegurar que coincidan con el orden de las categorías
            vals = [asset_class1[(asset_class1["Category"] == c) & (asset_class1["Period"] == p)]["Value"].values[0] 
                    if not asset_class1[(asset_class1["Category"] == c) & (asset_class1["Period"] == p)].empty else 0 
                    for c in categories]
            
            rects = ax.bar(x + (i - 1) * width, vals, width, label=p, color=color_map.get(p, "blue"))
            
            # Etiquetas de datos
            for rect in rects:
                h = rect.get_height()
                ax.annotate(f'{h:.1f}', xy=(rect.get_x() + rect.get_width()/2, h),
                            xytext=(0, 3 if h >= 0 else -12), textcoords="offset points",
                            ha='center', va='bottom' if h >= 0 else 'top', fontsize=8)

        ax.axhline(0, color='black', linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels([textwrap.fill(c, 12) for c in categories], fontsize=9)
        ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=3, frameon=False)
        plt.tight_layout()
        
        st.pyplot(fig)
    else:
        st.error("No se pudieron procesar los datos. Verifica la conexión o las APIs.")    



    st.header("Benchmark: Peruvian Mutual Funds")

    # 1) Definición de ETFs
    etfs = { 
        "FIXED INCOME": [
            ("AGG", "iShares Core U.S. Aggregate Bond ETF"), ("JNK", "SPDR Bloomberg High Yield Bond ETF"),
            ("HYG", "iShares iBoxx $ High Yield Corporate Bond ETF"), ("IB01.L", "iShares $ Treasury Bond 0-1yr UCITS ETF"),
            ("IUAG.L", "iShares US Aggregate Bond UCITS ETF USD"), ("GLAB.L", "SPDR Bloomberg Global Aggregate Bond"),
            ("BNDX", "Vanguard Total International Bond Index Fund"), ("IUSB", "iShares Core Universal USD Bond ETF"),
        ],
        "REAL ESTATE": [
            ("IFGL", "iShares International Developed Real Estate"), ("XLRE", "Real Estate Select Sector SPDR"),
            ("^FNER", "FTSE Nareit All Equity REITs Index"),
        ],
        "EQUITY": [
            ("JPEM", "JPMorgan Diversified Return Emerging Markets Equity"), ("ACWI", "iShares MSCI ACWI"),
            ("AAXJ", "iShares MSCI All Country Asia ex Japan"),
        ]
    }

    # 2) Configuración de Fechas
    today = datetime.today()
    start_ly = datetime(today.year - 1, 1, 1)
    end_ly = datetime(today.year - 1, 12, 31)
    start_ytd = datetime(today.year, 1, 1)

    @st.cache_data(ttl=3600)
    def get_plotly_data(_etfs_dict):
        rows = []
        for category, items in _etfs_dict.items():
            for ticker, name in items:
                try:
                    # Descargamos con un margen de seguridad para asegurar que asof encuentre datos
                    df = yf.download(ticker, start="2023-12-20", progress=False)
                    
                    if df.empty:
                        continue

                    # CORRECCIÓN CLAVE: Extraer 'Close' de forma plana independientemente del formato de Yahoo
                    if 'Close' in df.columns:
                        close_data = df['Close']
                        # Si es un DataFrame (MultiIndex), tomamos la primera columna
                        if isinstance(close_data, pd.DataFrame):
                            series = close_data.iloc[:, 0]
                        else:
                            series = close_data
                        
                        series = series.dropna()
                        
                        if series.empty:
                            continue

                        # Búsqueda robusta de precios (asof busca la fecha exacta o la anterior más cercana)
                        p_start_ly = series.loc[series.index.asof(pd.Timestamp(start_ly))]
                        p_end_ly = series.loc[series.index.asof(pd.Timestamp(end_ly))]
                        p_start_ytd = series.loc[series.index.asof(pd.Timestamp(start_ytd))]
                        p_now = series.iloc[-1]

                        last_year_ret = round(((p_end_ly / p_start_ly) - 1) * 100, 2)
                        ytd_ret = round(((p_now / p_start_ytd) - 1) * 100, 2)

                        rows.append({
                            "Category": category, 
                            "Name": name, 
                            "Last Year": last_year_ret, 
                            "YTD": ytd_ret
                        })
                except Exception as e:
                    print(f"Error en {ticker}: {e}")
                    continue
        return pd.DataFrame(rows)

    with st.spinner("Descargando y procesando datos de Yahoo Finance..."):
        df_bench = get_plotly_data(etfs)

    # 3) Construcción del Gráfico si hay datos
    if not df_bench.empty:
        fig = go.Figure()

        # Barra Año Pasado
        fig.add_trace(go.Bar(
            x=df_bench["Name"],
            y=df_bench["Last Year"],
            name=f"Año Pasado ({today.year - 1})",
            marker_color='silver',
            text=df_bench["Last Year"].apply(lambda x: f"{x}%"),
            textposition='outside',
            cliponaxis=False
        ))

        # Barra YTD
        fig.add_trace(go.Bar(
            x=df_bench["Name"],
            y=df_bench["YTD"],
            name="YTD",
            marker_color='#0A1A44',
            text=df_bench["YTD"].apply(lambda x: f"{x}%"),
            textposition='outside',
            cliponaxis=False
        ))

        # Layout y Estética
        fig.update_layout(
            title=dict(text="Useful Benchmark in Peruvian Mutual Funds", x=0.5, font=dict(size=20)),
            barmode='group',
            template="plotly_white",
            height=700,
            margin=dict(t=120, b=120, l=50, r=50),
            legend=dict(orientation="h", yanchor="bottom", y=-0.4, xanchor="center", x=0.5),
            yaxis_title="% Retorno",
            hovermode="x unified"
        )

        # Ajuste de etiquetas del Eje X
        fig.update_xaxes(
            tickvals=df_bench["Name"],
            ticktext=[label.replace(" ", "<br>") for label in df_bench["Name"]],
            tickfont=dict(size=10),
            showgrid=False
        )

        # 4) Divisores y Etiquetas de Categoría
        cumulative_count = 0
        # Calculamos el máximo para posicionar los títulos de categoría
        max_val = max(df_bench["Last Year"].max(), df_bench["YTD"].max())

        for category, items in etfs.items():
            count = len([x for x in df_bench["Category"] if x == category])
            if count == 0: continue
            
            if cumulative_count > 0:
                fig.add_vline(x=cumulative_count - 0.5, line_width=1, line_dash="dash", line_color="lightgray")
            
            fig.add_annotation(
                x=cumulative_count + (count-1)/2,
                y=1.1,
                yref="paper",
                text=f"<b>{category}</b>",
                showarrow=False,
                font=dict(size=13, color="black")
            )
            cumulative_count += count

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.error("No se pudieron obtener datos. Por favor, verifica tu conexión a internet o intenta recargar la página.")



