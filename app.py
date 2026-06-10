import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import math
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import date

st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="")

st.markdown("""
    <style>
        .stDataFrame div [role="gridcell"] > div { justify-content: center !important; text-align: center !important; }
        .stDataFrame div [role="columnheader"] > div { justify-content: center !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

def obter_precos_b3(tickers_lista):
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=7)
        return {t.upper(): float(dados[f"{t.upper()}.SA"]['Close'].ffill().iloc[-1]) for t in tickers_lista}
    except:
        return {t.upper(): 100.0 for t in tickers_lista}

def obter_preco_btc_brl():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl"
        resp = requests.get(url, timeout=7)
        preco = float(resp.json()['bitcoin']['brl'])
        if preco > 0:
            return preco
    except:
        pass
    try:
        btc_usd = float(requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=7).json()['data']['amount'])
        usd_brl = float(requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=7).json()['rates']['BRL'])
        if btc_usd > 0 and usd_brl > 0:
            return btc_usd * usd_brl
    except:
        pass
    try:
        dados = yf.download("BTC-BRL", period="2d", progress=False, auto_adjust=True, timeout=7)
        return float(dados['Close'].ffill().iloc[-1])
    except:
        pass
    return 0.0

def arredondar_teto(valor, multiplo):
    return math.ceil(valor / multiplo) * multiplo

def gerar_ticks_rs(y_max_rs, n_ticks=5):
    bruto = y_max_rs / (n_ticks - 1)
    magnitude = 10 ** math.floor(math.log10(bruto))
    candidatos = [magnitude, 2*magnitude, 5*magnitude, 10*magnitude]
    step = next(c for c in candidatos if c >= bruto)
    teto = arredondar_teto(y_max_rs, step)
    vals = [round(step * i) for i in range(n_ticks) if step * i <= teto + 1]
    return teto, vals

def gerar_ticks_pct(max_pct_ativo, step=5):
    teto = arredondar_teto(max_pct_ativo * 1.1, step)
    teto = max(teto, step)
    vals = list(range(0, teto + 1, step))
    return teto, vals

def abreviar_rs(valor):
    if valor >= 1_000_000:
        v = f"{valor/1_000_000:.1f}".replace('.', ',')
        return f"R$ {v}M"
    elif valor >= 1_000:
        v = valor / 1_000
        s = f"{v:.1f}".replace('.', ',')
        if s.endswith(',0'):
            s = s[:-2]
        return f"R$ {s}k"
    else:
        return f"R$ {int(valor)}"

def formatar_brl(valor):
    s = f"{valor:,.2f}"
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"R$ {s}"

# ── Tesouro Direto: lê de st.secrets, fallback para valor hardcoded ──────────
def preco_td_de_secrets(nome, fallback):
    try:
        return float(st.secrets["tesouro_direto"][nome])
    except:
        return fallback

def data_td_de_secrets(nome):
    try:
        return st.secrets["tesouro_direto_data"][nome]
    except:
        return "nao definida" 

MINHA_CARTEIRA = {
    'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
    'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
    'Cripto': {'BTC': 0.01492559},
    # (qtd, preco_fallback) — preco real vem de st.secrets
    'Tesouro Direto': {'Renda+ 2050': (24, 490.02)}
}

todos_b3 = [t for cls in ['ETF', 'FII'] for t in MINHA_CARTEIRA[cls].keys()]
precos = obter_precos_b3(todos_b3)
precos['BTC'] = obter_preco_btc_brl()

linhas = []
for cls, ativos in MINHA_CARTEIRA.items():
    for t, v in ativos.items():
        if isinstance(v, tuple):
            q        = v[0]
            prc      = preco_td_de_secrets(t, v[1])
        else:
            q   = v
            prc = precos.get(t.upper(), 0.0)
        linhas.append({'Ativo': t, 'Classe': cls, 'preco_unit': prc, 'Qtd': q, 'Total Atual': q * prc})

df = pd.DataFrame(linhas)
total_geral = df['Total Atual'].sum()
df['Part. %'] = (df['Total Atual'] / total_geral) * 100
df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values('Total Atual', ascending=False).reset_index(drop=True)
df_ativo = df.sort_values(by='Total Atual', ascending=False)

aba_dash, aba_detalhe, aba_lanc, aba_aportes = st.tabs(["dashboard", "detalhe", "lancamentos", "simular novos aportes"])

with aba_dash:
    st.metric("patrimonio total", formatar_brl(total_geral))

    st.markdown('---')

    col_donut, col_barras = st.columns([1, 2])

    with col_donut:
        total_classe = df_resumo_classe['Total Atual'].sum()
        labels_donut = []
        hover_donut  = []
        for _, row in df_resumo_classe.iterrows():
            pct     = row['Total Atual'] / total_classe * 100
            pct_str = f"{pct:.1f}%".replace('.', ',')
            rs_str  = formatar_brl(row['Total Atual'])
            labels_donut.append(f"{row['Classe']}<br>{pct_str}")
            hover_donut.append(f"<b>{row['Classe']}</b><br>{pct_str}<br>{rs_str}")

        fig_donut = go.Figure(go.Pie(
            labels=labels_donut,
            values=df_resumo_classe['Total Atual'].tolist(),
            hole=0.75,
            textinfo='label',
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover_donut,
            marker=dict(colors=px.colors.sequential.Blues_r[:len(df_resumo_classe)]),
            domain=dict(x=[0.1, 0.9], y=[0.1, 0.9])
        ))
        fig_donut.update_layout(
            margin=dict(t=60, b=60, l=60, r=60),
            height=400,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_barras:
        max_pct = df_ativo['Part. %'].max()
        max_rs  = df_ativo['Total Atual'].max()

        y_max_pct, ticks_pct = gerar_ticks_pct(max_pct, step=5)

        # ticks % visiveis: apenas os menores que o maximo real
        ticks_pct_show = [v for v in ticks_pct if v <= max_pct]

        # eixo direito: mesmos pontos do eixo %, convertidos para R$
        # tick_rs = tick_pct / 100 * total_geral  (escala perfeita)
        ticks_rs_labels = [f"R$ {v/100*total_geral:,.0f}".replace(',', '.') for v in ticks_pct_show]

        shapes = []
        for p in ticks_pct_show[1:]:
            shapes.append(dict(
                type='line', xref='paper', x0=0, x1=1,
                yref='y', y0=p, y1=p,
                line=dict(color='rgba(255,255,255,0.08)', width=1, dash='dot')
            ))

        hover_barras = [
            f"<b>{row['Ativo']}</b><br>{str(round(row['Part. %'], 2)).replace('.', ',')}%<br>{formatar_brl(row['Total Atual'])}"
            for _, row in df_ativo.iterrows()
        ]

        fig_ativo = go.Figure()
        fig_ativo.add_trace(
            go.Bar(
                x=df_ativo['Ativo'], y=df_ativo['Part. %'],
                marker_color='#1E88E5',
                text=df_ativo['Ativo'],
                textposition='outside', textangle=-90,
                textfont=dict(size=9, color='white'),
                cliponaxis=False,
                hovertemplate='%{customdata}<extra></extra>',
                customdata=hover_barras,
                yaxis='y'
            )
        )
        # trace invisivel no yaxis2 para forca-lo a aparecer
        fig_ativo.add_trace(
            go.Scatter(
                x=[df_ativo['Ativo'].iloc[0]],
                y=[0],
                mode='markers',
                marker=dict(color='rgba(0,0,0,0)', size=0),
                hoverinfo='skip',
                showlegend=False,
                yaxis='y2'
            )
        )

        fig_ativo.update_layout(
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            shapes=shapes,
            xaxis=dict(showticklabels=False),
            bargap=0.15,
            margin=dict(t=10, b=10, l=10, r=10)
        )
        # eixo esquerdo: part. %
        fig_ativo.update_yaxes(
            title_text="",
            showgrid=True, gridcolor='#333', side='left',
            range=[0, y_max_pct * 1.2],
            tickvals=ticks_pct_show,
            ticktext=[f"{str(v).replace('.', ',')}%" for v in ticks_pct_show]
        )

        # eixo direito: mesmo range e mesmos pontos do eixo %
        # labels convertidos para R$ — escala perfeitamente alinhada
        fig_ativo.update_layout(
            yaxis2=dict(
                overlaying='y',
                side='right',
                showgrid=False,
                range=[0, y_max_pct * 1.2],
                tickvals=ticks_pct_show,
                ticktext=ticks_rs_labels,
                title_text=""
            )
        )
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    avisos = []
    for cls, ativos in MINHA_CARTEIRA.items():
        for nome, v in ativos.items():
            if isinstance(v, tuple):
                prc_atual  = preco_td_de_secrets(nome, v[1])
                data_atual = data_td_de_secrets(nome)
                avisos.append(f"**{nome}**: {formatar_brl(prc_atual)} · atualizado em {data_atual}")
    if avisos:
        st.caption("preco manual (atualize em Settings > Secrets): " + " · ".join(avisos))

    df_display = df.copy()
    df_display['preco_unit']  = df_display['preco_unit'].apply(formatar_brl)
    df_display['Total Atual'] = df_display['Total Atual'].apply(formatar_brl)
    df_display['Part. %']     = df_display['Part. %'].apply(lambda x: f"{x:.2f}%".replace('.', ','))
    df_display['Qtd']         = df_display['Qtd'].apply(lambda x: f"{x:g}".replace('.', ','))

    config = {
        'Ativo':       st.column_config.TextColumn("ativo",          alignment="center"),
        'Classe':      st.column_config.TextColumn("classe",         alignment="center"),
        'preco_unit':  st.column_config.TextColumn("preco unidade",  alignment="center"),
        'Qtd':         st.column_config.TextColumn("qtd",            alignment="center"),
        'Total Atual': st.column_config.TextColumn("total atual",    alignment="center"),
        'Part. %':     st.column_config.TextColumn("part. %",        alignment="center"),
    }
    st.dataframe(df_display, use_container_width=True, hide_index=True, column_config=config)

# ── Google Sheets helpers ─────────────────────────────────────────────────────
def get_sheets_service():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds).spreadsheets()

SHEET_ID  = st.secrets["google_sheets"]["spreadsheet_id"]
SHEET_TAB = "lancamentos"
HEADERS   = ["data", "tipo", "ativo", "classe", "quantidade", "preco_unitario", "total", "observacao"]

@st.cache_data(ttl=30)
def ler_lancamentos():
    try:
        svc  = get_sheets_service()
        res  = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A:H").execute()
        rows = res.get("values", [])
        if len(rows) <= 1:
            return pd.DataFrame(columns=HEADERS)
        df_l = pd.DataFrame(rows[1:], columns=HEADERS)
        df_l["quantidade"]    = pd.to_numeric(df_l["quantidade"],    errors="coerce")
        df_l["preco_unitario"]= pd.to_numeric(df_l["preco_unitario"],errors="coerce")
        df_l["total"]         = pd.to_numeric(df_l["total"],         errors="coerce")
        return df_l
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return pd.DataFrame(columns=HEADERS)

def salvar_lancamento(row: list):
    svc = get_sheets_service()
    svc.values().append(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_TAB}!A:H",
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()
    st.cache_data.clear()

def deletar_lancamento(idx_linha_sheet: int):
    # idx_linha_sheet: 1-based, linha 1 = header
    svc = get_sheets_service()
    body = {"requests": [{"deleteDimension": {"range": {
        "sheetId": 0,
        "dimension": "ROWS",
        "startIndex": idx_linha_sheet,
        "endIndex":   idx_linha_sheet + 1
    }}}]}
    svc.batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
    st.cache_data.clear()

def garantir_cabecalho():
    try:
        svc = get_sheets_service()
        res = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A1:H1").execute()
        if not res.get("values"):
            svc.values().update(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [HEADERS]}
            ).execute()
    except:
        pass

garantir_cabecalho()

# ── Aba lancamentos ────────────────────────────────────────────────────────────
with aba_lanc:

    df_lanc = ler_lancamentos()

    # ── Formulario de novo lancamento ─────────────────────────────────────────
    with st.expander("+ novo lancamento", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            f_data  = st.date_input("data", value=date.today())
            f_tipo  = st.selectbox("tipo", ["compra", "venda"])
        with col2:
            todos_ativos = sorted([t for cls in MINHA_CARTEIRA.values() for t in cls.keys()])
            f_ativo = st.selectbox("ativo", todos_ativos)
            f_classe = next((cls for cls, atv in MINHA_CARTEIRA.items()
                             for t, v in atv.items() if t == f_ativo), "")
            st.text_input("classe", value=f_classe, disabled=True)
        with col3:
            f_qtd   = st.number_input("quantidade", min_value=0.0, step=0.001, format="%.6f")
            f_preco = st.number_input("preco unitario (R$)", min_value=0.0, step=0.01, format="%.2f")
        with col4:
            f_total = f_qtd * f_preco
            st.metric("total", formatar_brl(f_total))
            f_obs   = st.text_input("observacao (opcional)")

        if st.button("salvar lancamento", type="primary"):
            if f_qtd > 0 and f_preco > 0:
                salvar_lancamento([
                    f_data.strftime("%d/%m/%Y"),
                    f_tipo, f_ativo, f_classe,
                    f_qtd, f_preco, round(f_total, 2), f_obs
                ])
                st.success("lancamento salvo!")
                st.rerun()
            else:
                st.warning("preencha quantidade e preco.")

    st.markdown("---")

    if df_lanc.empty:
        st.info("nenhum lancamento registrado ainda.")
    else:
        # ── Tabela de lancamentos com exclusao ───────────────────────────────
        st.subheader("historico")

        col_del, col_tabela = st.columns([0.08, 0.92])
        with col_tabela:
            df_lanc_fmt = df_lanc.copy()
            df_lanc_fmt["preco_unitario"] = df_lanc_fmt["preco_unitario"].apply(
                lambda x: formatar_brl(x) if pd.notna(x) else "")
            df_lanc_fmt["total"] = df_lanc_fmt["total"].apply(
                lambda x: formatar_brl(x) if pd.notna(x) else "")
            df_lanc_fmt["quantidade"] = df_lanc_fmt["quantidade"].apply(
                lambda x: f"{x:g}".replace(".", ",") if pd.notna(x) else "")

            cfg_lanc = {c: st.column_config.TextColumn(c, alignment="center") for c in HEADERS}
            st.dataframe(df_lanc_fmt, use_container_width=True, hide_index=False, column_config=cfg_lanc)

        st.markdown("---")

        # exclusao por indice
        with st.expander("excluir lancamento"):
            idx_del = st.number_input(
                "numero da linha (conforme tabela acima, começa em 0)",
                min_value=0, max_value=max(0, len(df_lanc)-1), step=1
            )
            if st.button("excluir", type="secondary"):
                deletar_lancamento(idx_del + 1)  # +1 pula o header
                st.success("lancamento excluido!")
                st.rerun()

        st.markdown("---")

        # ── Preco medio por ativo ────────────────────────────────────────────
        st.subheader("preco medio por ativo")
        compras = df_lanc[df_lanc["tipo"] == "compra"].copy()
        if not compras.empty:
            # calcular saldo por ativo (compras - vendas)
            df_lanc["sinal"] = df_lanc["tipo"].map({"compra": 1, "venda": -1}).fillna(0)
            saldo_ativo = df_lanc.groupby("ativo").apply(
                lambda g: (g["quantidade"] * g["sinal"]).sum()
            ).reset_index()
            saldo_ativo.columns = ["ativo", "saldo"]
            ativos_ativos = saldo_ativo[saldo_ativo["saldo"] > 0]["ativo"].tolist()

            pm = compras[compras["ativo"].isin(ativos_ativos)].groupby("ativo").apply(
                lambda g: pd.Series({
                    "total investido": (g["quantidade"] * g["preco_unitario"]).sum(),
                    "qtd comprada":     g["quantidade"].sum(),
                    "preco medio":     (g["quantidade"] * g["preco_unitario"]).sum() / g["quantidade"].sum()
                })
            ).reset_index()
            pm_fmt = pm.copy()
            pm_fmt["total investido"] = pm_fmt["total investido"].apply(formatar_brl)
            pm_fmt["qtd total"]       = pm_fmt["qtd total"].apply(lambda x: f"{x:g}".replace(".", ","))
            pm_fmt["preco medio"]     = pm_fmt["preco medio"].apply(formatar_brl)
            cfg_pm = {c: st.column_config.TextColumn(c, alignment="center") for c in pm_fmt.columns}
            st.dataframe(pm_fmt, use_container_width=True, hide_index=True, column_config=cfg_pm)

        st.markdown("---")

        # ── Evolucao do patrimônio (por data de lancamento) ──────────────────
        st.subheader("evolucao do patrimonio investido")
        df_evo = df_lanc.copy()
        df_evo["data_dt"] = pd.to_datetime(df_evo["data"], format="%d/%m/%Y", errors="coerce")
        df_evo = df_evo.dropna(subset=["data_dt"]).sort_values("data_dt")
        df_evo["sinal"]  = df_evo["tipo"].map({"compra": 1, "venda": -1}).fillna(0)
        df_evo["valor"]  = df_evo["total"] * df_evo["sinal"]
        df_evo["acum"]   = df_evo["valor"].cumsum()

        fig_evo = go.Figure()
        fig_evo.add_trace(go.Scatter(
            x=df_evo["data_dt"], y=df_evo["acum"],
            mode="lines+markers",
            line=dict(color="#1E88E5", width=2),
            marker=dict(size=5),
            hovertemplate="%{x|%d/%m/%Y}<br>" + formatar_brl(0).replace("0", "%{y:,.2f}") + "<extra></extra>"
        ))
        fig_evo.update_layout(
            height=300,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#333")
        )
        st.plotly_chart(fig_evo, use_container_width=True)
