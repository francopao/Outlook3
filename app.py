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
# --------------------------------------
# SCRAPER Y TRANSFORMADOR DE DATOS
# --------------------------------------

@st.cache_data
def obtener_datos_tesoro(periodos):
    all_data = []
    headers = []
    for year in periodos:
        url = f'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve&field_tdr_date_value={year}'
        response = requests.get(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', {'class': 'usa-table views-table views-view-table cols-26'})
            if table:
                headers = [header.text.strip() for header in table.find_all('th')]
                for row in table.find_all('tr')[1:]:
                    cells = [year] + [cell.text.strip() for cell in row.find_all('td')]
                    all_data.append(cells)

    if all_data:
        headers = ['Year'] + headers
        df = pd.DataFrame(all_data, columns=headers)
        df = df.drop(columns=['1.5 Mo'], errors='ignore')
        df = df.apply(lambda x: x.replace('N/A', pd.NA) if x.dtype == "object" else x)
        df = df.dropna(axis=1, how='all')
        df = df.fillna(0)
        for col in df.columns[2:]:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date")
        return df
    else:
        return pd.DataFrame()

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
    fred = Fred(api_key='762e2ee1c8fab5d038ce317929d47226')
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
        "Gold": "GOLD",
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


     # --- Inputs de imagen de barras
    @st.cache_data(show_spinner=False)
    def load_asset_class1():
        benchmark1 = load_benchmarks()
        return compute_period_returns(benchmark1)

    benchmark1 = load_benchmarks()
    asset_class1 = load_asset_class1()

    
  


    # ---- Cálculo de rentabilidades ----
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

    # ---- DataFrame final ----
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

    st.markdown("### Asset Class Performance")

    fig, ax = plt.subplots(figsize=(18, 6))

    unique_periods = asset_class1["Period"].unique()
    period_year  = [p for p in unique_periods if p != "YTD" and p[:3].isdigit()]
    period_ytd   = ["YTD"]
    period_other = [p for p in unique_periods if p not in period_year and p != "YTD"]
    periods = period_year + period_ytd + period_other

    color_map = {
        periods[0]: "black",
        periods[1]: "gray",
        periods[2]: "red"
    }

    categories = asset_class1["Category"].unique()
    x = np.arange(len(categories))
    width = 0.28
    bars = {}

    for i, period in enumerate(periods):
        subset = asset_class1[asset_class1["Period"] == period]
        values = subset["Value"].values
        offset = (i - 1) * width
        bars[period] = ax.bar(
            x + offset,
            values,
            width,
            color=color_map[period],
            label=period
        )

    def add_labels(bar_container):
        for bar in bar_container:
            h = bar.get_height()
            offset = max(0.03 * abs(h), 0.5)
            y = h + offset if h >= 0 else h - offset
            ax.text(bar.get_x() + bar.get_width()/2, y, f"{h:.1f}",
                    ha="center", va="bottom" if h >= 0 else "top", fontsize=9)

    for period in periods:
        add_labels(bars[period])

    ax.axhline(0, color="black", linewidth=1)

    wrapped = ["\n".join(textwrap.wrap(c, 18)) for c in categories]
    ax.set_xticks(x)
    ax.set_xticklabels(wrapped, fontsize=10)
    ax.set_ylabel("%")

    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20),
              ncol=3, frameon=False)

    fig.tight_layout()
    st.pyplot(fig)





