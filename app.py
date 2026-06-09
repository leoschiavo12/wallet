import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import math
import requests

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

aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "simular novos aportes"])

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
