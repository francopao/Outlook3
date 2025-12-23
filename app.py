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
@st.cache_data



def obtener_datos_tesoro(periodos):
    all_data = []

    headers_req = {
        "User-Agent": "Mozilla/5.0"
    }

    for year in periodos:
        url = (
            "https://home.treasury.gov/resource-center/data-chart-center/"
            "interest-rates/TextView"
            f"?type=daily_treasury_yield_curve&field_tdr_date_value={year}"
        )

        response = requests.get(url, headers=headers_req, timeout=30)

        if response.status_code != 200:
            continue

        soup = BeautifulSoup(response.text, "html.parser")

        table = soup.find("table", id="DataTables_Table_0")
        if table is None:
            continue

        # Headers
        headers = [th.get_text(strip=True) for th in table.find("thead").find_all("th")]

        # Filas
        rows = []
        for tr in table.find("tbody").find_all("tr"):
            rows.append([td.get_text(strip=True) for td in tr.find_all("td")])

        if not rows:
            continue

        df_year = pd.DataFrame(rows, columns=headers)

        # Tipos y limpieza
        df_year["Date"] = pd.to_datetime(df_year["Date"], errors="coerce")
        df_year["Year"] = year

        all_data.append(df_year)

    if not all_data:
        return pd.DataFrame()

    df = pd.concat(all_data, ignore_index=True)

    # Mantener tu lógica original
    df = df.drop(columns=["1.5 Mo"], errors="ignore")
    df = df.replace("N/A", pd.NA)
    df = df.dropna(axis=1, how="all")
    df = df.fillna(0)

    for col in df.columns:
        if col not in ["Date", "Year"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.sort_values("Date").reset_index(drop=True)

    return df



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
st.image("https://media.licdn.com/dms/image/v2/D4E03AQHNhGZoA9sCQA/profile-displayphoto-shrink_200_200/B4EZahq4dLGQAg-/0/1746469097627?e=2147483647&v=beta&t=hAA0K9UwE_sigpOhx5y4U4soabNV6x8H8O-VZBDvhbM", 
         width=200)
st.title("Global Fixed Income Dashboard - Franco Olivares")

tab1, tab2, tab3, tab4 = st.tabs(["Treasury Yields", "US Corporate Bonds", "US Labor Market", "Equity"])

# --------------------------------------
# TAB 1: CURVAS DEL TESORO
# --------------------------------------    
with tab1:
    años = st.multiselect("Selecciona año(s):", list(range(2006, 2026)), default=[2025])
    df = obtener_datos_tesoro(años)

    if not df.empty:
        st.success(f"{df.shape[0]} registros obtenidos.")

        fechas = sorted(df["Date"].unique())
        fechas_seleccionadas = st.multiselect("Selecciona una o más fechas para comparar curvas:", fechas[-10:], default=fechas[-3:])

        if "10 Yr" in df.columns and "2 Yr" in df.columns:
            df["Spread 10Y - 2Y"] = df["10 Yr"] - df["2 Yr"]
            st.metric("📉 Spread 10Y - 2Y actual", f"{df['Spread 10Y - 2Y'].iloc[-1]:.2f} %")
            fig_spread = px.line(df, x="Date", y="Spread 10Y - 2Y", title="Evolución del Spread 10Y - 2Y")
            st.plotly_chart(fig_spread, use_container_width=True)

        st.subheader("Comparación de curvas por fecha")
        fig_comparacion = px.line()

        for fecha in fechas_seleccionadas:
            datos_fecha = df[df["Date"] == fecha].iloc[0]
            maturities = df.columns[2:-2]
            tasas = datos_fecha[maturities].values.astype(float)
            fig_comparacion.add_scatter(x=maturities, y=tasas, mode="lines+markers", name=str(fecha.date()))

        fig_comparacion.update_layout(title="Curvas de rendimiento comparadas", xaxis_title="Plazo", yaxis_title="Rendimiento (%)")
        st.plotly_chart(fig_comparacion, use_container_width=True)

        st.subheader("Rendimiento de los bonos del Tesoro a la par")
        df_anim = df.copy()
        df_anim = df_anim.melt(id_vars=["Date"], value_vars=maturities, var_name="Maturity", value_name="Yield")

        fig_anim = px.line(df_anim, x="Maturity", y="Yield", animation_frame=df_anim["Date"].dt.strftime("%Y-%m-%d"),
                        title="Evolución diaria de la curva de rendimiento")
        fig_anim.update_layout(xaxis_title="Plazo", yaxis_title="Rendimiento (%)")
        st.plotly_chart(fig_anim, use_container_width=True)

        st.subheader("Exportar datos")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Yield Curve')
            if "Spread 10Y - 2Y" in df.columns:
                df[['Date', 'Spread 10Y - 2Y']].to_excel(writer, index=False, sheet_name='Spread')

        st.download_button(label="⬇️ Descargar Excel", data=output.getvalue(), file_name="treasury_yield_curve.xlsx")

    else:
        st.warning("No se encontraron datos para los años seleccionados.")



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
    current_year = datetime.now().year
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



