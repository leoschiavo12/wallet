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
        /* amarelo claro na coluna editavel */
        [data-testid="stDataEditor"] div[role="gridcell"][aria-colindex="4"] {
            background-color: rgba(255, 230, 100, 0.12) !important;
        }
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

MINHA_CARTEIRA = {
    'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
    'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
    'Cripto': {'BTC': 0.01492559},
    # Tesouro Direto: {nome: (qtd_unidades, preco_unitario_venda)}
    # Atualize o preco diretamente na tabela da aba "detalhe"
    'Tesouro Direto': {'Renda+ 2050': (22.5, 4906.40)}
}

todos_b3 = [t for cls in ['ETF', 'FII'] for t in MINHA_CARTEIRA[cls].keys()]
precos = obter_precos_b3(todos_b3)
precos['BTC'] = obter_preco_btc_brl()

# inicializar precos do TD no session_state (persiste durante a sessao)
if 'precos_td' not in st.session_state:
    st.session_state.precos_td = {
        nome: v[1]
        for cls, ativos in MINHA_CARTEIRA.items()
        for nome, v in ativos.items()
        if isinstance(v, tuple)
    }

linhas = []
for cls, ativos in MINHA_CARTEIRA.items():
    for t, v in ativos.items():
        if isinstance(v, tuple):
            q   = v[0]
            prc = st.session_state.precos_td.get(t, v[1])
        else:
            q   = v
            prc = precos.get(t.upper(), 0.0)
        linhas.append({'Ativo': t, 'Classe': cls, 'preco_unit': prc, 'editavel': isinstance(v, tuple), 'Qtd': q, 'Total Atual': q * prc})

df = pd.DataFrame(linhas)
total_geral = df['Total Atual'].sum()
df['Part. %'] = (df['Total Atual'] / total_geral) * 100
df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values('Total Atual', ascending=False).reset_index(drop=True)
df_ativo = df.sort_values(by='Total Atual', ascending=False)

aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "simular novos aportes"])

with aba_dash:
    st.metric("patrimonio total", formatar_brl(total_geral))

    avisos = []
    for cls, ativos in MINHA_CARTEIRA.items():
        for nome, v in ativos.items():
            if isinstance(v, tuple):
                prc_atual = st.session_state.precos_td.get(nome, v[1])
                avisos.append(f"**{nome}**: {formatar_brl(prc_atual)} — atualize na aba detalhe")
    if avisos:
        st.caption("preco manual: " + " · ".join(avisos))

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
            textfont=dict(size=11),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover_donut,
            marker=dict(colors=px.colors.sequential.Blues_r[:len(df_resumo_classe)])
        ))
        fig_donut.update_layout(
            margin=dict(t=40, b=40, l=40, r=40),
            height=350,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_barras:
        max_pct = df_ativo['Part. %'].max()
        max_rs  = df_ativo['Total Atual'].max()

        y_max_pct, ticks_pct = gerar_ticks_pct(max_pct, step=5)
        y_max_rs,  ticks_rs  = gerar_ticks_rs(max_rs * (y_max_pct / max_pct))

        ticks_pct_show = ticks_pct[:-1]
        ticks_rs_show  = ticks_rs[:-1]

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

        fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ativo.add_trace(
            go.Bar(
                x=df_ativo['Ativo'], y=df_ativo['Part. %'],
                marker_color='#1E88E5',
                text=df_ativo['Ativo'],
                textposition='outside', textangle=-90,
                textfont=dict(size=9, color='white'),
                cliponaxis=False,
                hovertemplate='%{customdata}<extra></extra>',
                customdata=hover_barras
            ),
            secondary_y=False
        )
        fig_ativo.add_trace(
            go.Scatter(
                x=df_ativo['Ativo'], y=df_ativo['Total Atual'],
                mode='markers', marker=dict(color='rgba(0,0,0,0)'),
                hoverinfo='skip'
            ),
            secondary_y=True
        )
        fig_ativo.update_layout(
            height=350, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False, shapes=shapes, xaxis=dict(showticklabels=False)
        )
        fig_ativo.update_yaxes(
            title_text="part. %", secondary_y=False,
            showgrid=True, gridcolor='#333', side='left',
            range=[0, y_max_pct * 1.35],
            tickvals=ticks_pct_show,
            ticktext=[f"{str(v).replace('.', ',')}%" for v in ticks_pct_show]
        )
        fig_ativo.update_yaxes(
            title_text="total (R$)", secondary_y=True,
            showgrid=False, side='right',
            range=[0, y_max_rs * 1.35],
            tickvals=ticks_rs_show,
            ticktext=[abreviar_rs(v) for v in ticks_rs_show]
        )
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    st.caption("celulas amarelas sao editaveis. altere o preco e pressione Enter para atualizar.")

    # preparar df para edicao: preco_unit como float para ser editavel
    df_edit = df[['Ativo', 'Classe', 'editavel', 'preco_unit', 'Qtd', 'Total Atual', 'Part. %']].copy()

    # formatar colunas nao editaveis para exibicao
    df_edit['Qtd_fmt']         = df_edit['Qtd'].apply(lambda x: f"{x:g}".replace('.', ','))
    df_edit['Total Atual_fmt'] = df_edit['Total Atual'].apply(formatar_brl)
    df_edit['Part. %_fmt']     = df_edit['Part. %'].apply(lambda x: f"{x:.2f}%".replace('.', ','))

    config_edit = {
        'Ativo':           st.column_config.TextColumn("ativo",         disabled=True,  alignment="center"),
        'Classe':          st.column_config.TextColumn("classe",        disabled=True,  alignment="center"),
        'preco_unit':      st.column_config.NumberColumn(
                               "preco unidade",
                               disabled=False,
                               format="%.2f",
                               min_value=0.0,
                               help="Editavel apenas para Tesouro Direto"
                           ),
        'Qtd_fmt':         st.column_config.TextColumn("qtd",           disabled=True,  alignment="center"),
        'Total Atual_fmt': st.column_config.TextColumn("total atual",   disabled=True,  alignment="center"),
        'Part. %_fmt':     st.column_config.TextColumn("part. %",       disabled=True,  alignment="center"),
        'editavel':        None,  # ocultar coluna auxiliar
        'Qtd':             None,
        'Total Atual':     None,
        'Part. %':         None,
    }

    # highlight linhas editaveis via styler
    def highlight_td(row):
        if row['editavel']:
            return [''] * 2 + ['background-color: rgba(255,220,50,0.18); color: #ffe066'] + [''] * 3
        return [''] * 6

    df_styled = df_edit[['Ativo', 'Classe', 'preco_unit', 'Qtd_fmt', 'Total Atual_fmt', 'Part. %_fmt', 'editavel']].style.apply(highlight_td, axis=1)

    edited = st.data_editor(
        df_edit[['Ativo', 'Classe', 'preco_unit', 'Qtd_fmt', 'Total Atual_fmt', 'Part. %_fmt', 'editavel']],
        column_config=config_edit,
        hide_index=True,
        use_container_width=True,
        key='editor_detalhe'
    )

    # detectar mudanca no preco_unit de linhas editaveis e atualizar session_state
    for i, row in edited.iterrows():
        if row['editavel']:
            ativo = row['Ativo']
            novo_preco = float(row['preco_unit'])
            if novo_preco != st.session_state.precos_td.get(ativo, 0.0):
                st.session_state.precos_td[ativo] = novo_preco
                st.rerun()
