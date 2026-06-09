import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import math

st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="")

st.markdown("""
    <style>
        .stDataFrame th { text-align: center !important; }
        .stDataFrame td { text-align: center !important; }
        .stDataFrame div [role="gridcell"] { justify-content: center !important; }
        .stDataFrame div [role="gridcell"] > div { justify-content: center !important; text-align: center !important; }
        .stDataFrame div [role="columnheader"] { justify-content: center !important; }
        .stDataFrame div [role="columnheader"] > div { justify-content: center !important; text-align: center !important; }
        [data-testid="stDataFrameResizable"] div[role="columnheader"] span { width: 100% !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

def obter_precos_b3(tickers_lista):
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=7)
        return {t.upper(): float(dados[f"{t.upper()}.SA"]['Close'].ffill().iloc[-1]) for t in tickers_lista}
    except:
        return {t.upper(): 100.0 for t in tickers_lista}

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
    'Tesouro Direto': {'Renda+ 2050': 22.5}
}

todos_b3 = [t for cls in ['ETF', 'FII'] for t in MINHA_CARTEIRA[cls].keys()]
precos = obter_precos_b3(todos_b3)

linhas = []
for cls, ativos in MINHA_CARTEIRA.items():
    for t, q in ativos.items():
        prc = precos.get(t.upper(), 385000 if t == 'BTC' else 490.64)
        linhas.append({'ativo': t, 'classe': cls, 'preco_unit': prc, 'qtd': q, 'total atual': q * prc})

df = pd.DataFrame(linhas)
total_geral = df['total atual'].sum()
df['part. %'] = (df['total atual'] / total_geral) * 100
df_resumo_classe = df.groupby('classe')['total atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values('total atual', ascending=False).reset_index(drop=True)
df_ativo = df.sort_values(by='total atual', ascending=False)

ALTURA = 340

aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "simular novos aportes"])

with aba_dash:

    st.metric("patrimonio total", formatar_brl(total_geral))
    st.markdown('---')

    col_donut, col_barras = st.columns([1, 2])

    with col_donut:
        total_classe = df_resumo_classe['total atual'].sum()
        labels_donut = []
        hover_donut  = []
        for _, row in df_resumo_classe.iterrows():
            pct     = row['total atual'] / total_classe * 100
            pct_str = f"{pct:.1f}%".replace('.', ',')
            rs_str  = formatar_brl(row['total atual'])
            labels_donut.append(f"{row['classe']}<br>{pct_str}")
            hover_donut.append(f"<b>{row['classe']}</b><br>{pct_str}<br>{rs_str}")

        fig_donut = go.Figure(go.Pie(
            labels=labels_donut,
            values=df_resumo_classe['total atual'].tolist(),
            hole=0.65,
            textinfo='label',
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover_donut,
            marker=dict(colors=px.colors.sequential.Blues_r[:len(df_resumo_classe)]),
            domain=dict(x=[0.05, 0.95], y=[0.05, 0.95])
        ))
        fig_donut.update_layout(
            margin=dict(t=60, b=60, l=70, r=70),
            height=ALTURA,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_barras:
        max_pct = df_ativo['part. %'].max()
        max_rs  = df_ativo['total atual'].max()

        y_max_pct, ticks_pct = gerar_ticks_pct(max_pct, step=5)
        y_max_rs,  ticks_rs  = gerar_ticks_rs(max_rs * (y_max_pct / max_pct))

        shapes = []
        for p in ticks_pct[1:-1]:
            shapes.append(dict(
                type='line', xref='paper', x0=0, x1=1,
                yref='y', y0=p, y1=p,
                line=dict(color='rgba(255,255,255,0.08)', width=1, dash='dot')
            ))

        hover_barras = [
            f"<b>{row['ativo']}</b><br>{str(round(row['part. %'], 2)).replace('.', ',')}%<br>{formatar_brl(row['total atual'])}"
            for _, row in df_ativo.iterrows()
        ]

        fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])

        fig_ativo.add_trace(
            go.Bar(
                x=df_ativo['ativo'],
                y=df_ativo['part. %'],
                marker_color='#1E88E5',
                text=df_ativo['ativo'],
                textposition='outside',
                textangle=-90,
                textfont=dict(size=9, color='white'),
                cliponaxis=False,
                hovertemplate='%{customdata}<extra></extra>',
                customdata=hover_barras
            ),
            secondary_y=False
        )

        fig_ativo.add_trace(
            go.Scatter(
                x=df_ativo['ativo'],
                y=df_ativo['total atual'],
                mode='markers',
                marker=dict(color='rgba(0,0,0,0)'),
                hoverinfo='skip'
            ),
            secondary_y=True
        )

        ticks_pct_show = ticks_pct[:-1]
        ticks_rs_show  = ticks_rs[:-1]

        fig_ativo.update_layout(
            height=ALTURA,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            shapes=shapes,
            margin=dict(t=60, b=60, l=70, r=70),
            xaxis=dict(showticklabels=False)
        )

        fig_ativo.update_yaxes(
            title_text="part. %",
            secondary_y=False,
            showgrid=True, gridcolor='#333',
            side='left',
            range=[0, y_max_pct * 1.35],
            tickvals=ticks_pct_show,
            ticktext=[f"{str(v).replace('.', ',')}%" for v in ticks_pct_show]
        )

        fig_ativo.update_yaxes(
            title_text="total (R$)",
            secondary_y=True,
            showgrid=False,
            side='right',
            range=[0, y_max_rs * 1.35],
            tickvals=ticks_rs_show,
            ticktext=[abreviar_rs(v) for v in ticks_rs_show]
        )

        st.plotly_chart(fig_ativo, use_container_width=True)


with aba_detalhe:
    df_display = df.copy()
    df_display['preco_unit']  = df_display['preco_unit'].apply(formatar_brl)
    df_display['total atual'] = df_display['total atual'].apply(formatar_brl)
    df_display['part. %']     = df_display['part. %'].apply(lambda x: f"{x:.2f}%".replace('.', ','))
    df_display['qtd']         = df_display['qtd'].apply(lambda x: f"{x:g}".replace('.', ','))

    config = {
        'ativo':       st.column_config.TextColumn("ativo",          alignment="center"),
        'classe':      st.column_config.TextColumn("classe",         alignment="center"),
        'preco_unit':  st.column_config.TextColumn("preco unitario", alignment="center"),
        'qtd':         st.column_config.TextColumn("qtd",            alignment="center"),
        'total atual': st.column_config.TextColumn("total atual",    alignment="center"),
        'part. %':     st.column_config.TextColumn("part. %",        alignment="center"),
    }
    st.dataframe(df_display, use_container_width=True, hide_index=True, column_config=config)
