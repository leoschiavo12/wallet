import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io

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

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) / 255.0 for i in (0, 2, 4))

def render_donut(labels, values, hex_colors, bg='#0e1117'):
    cores_rgb = [hex_to_rgb(c) for c in hex_colors]
    bg_rgb    = hex_to_rgb(bg)

    fig, ax = plt.subplots(figsize=(3.5, 3.5), facecolor=bg_rgb)
    ax.set_facecolor(bg_rgb)

    wedges, _, autotexts = ax.pie(
        values,
        labels=None,
        autopct='%1.1f%%',
        startangle=90,
        counterclock=True,
        colors=cores_rgb,
        wedgeprops=dict(width=0.42, edgecolor=bg_rgb, linewidth=1.5),
        pctdistance=0.78
    )

    for at in autotexts:
        at.set_color('white')
        at.set_fontsize(8)

    total = sum(values)
    for wedge, label, val in zip(wedges, labels, values):
        ang     = (wedge.theta1 + wedge.theta2) / 2
        ang_rad = math.radians(ang)
        x = math.cos(ang_rad)
        y = math.sin(ang_rad)
        ax.annotate(
            f"{label}\n{val/total*100:.1f}%",
            xy=(0.6*x, 0.6*y),
            xytext=(1.22*x, 1.22*y),
            ha='center', va='center',
            color='white', fontsize=7.5,
            arrowprops=dict(arrowstyle='-', color='#444444', lw=0.7)
        )

    ax.set_xlim(-1.65, 1.65)
    ax.set_ylim(-1.65, 1.65)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor=bg_rgb, dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf

MINHA_CARTEIRA = {
    'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
    'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
    'Cripto': {'BTC': 0.01492559},
    'Tesouro Direto': {'Renda+ 2050': 22.5}
}

todos_b3 = [t for cls in ['ETF', 'FII'] for t in MINHA_CARTEIRA[cls].keys()]
precos   = obter_precos_b3(todos_b3)

linhas = []
for cls, ativos in MINHA_CARTEIRA.items():
    for t, q in ativos.items():
        prc = precos.get(t.upper(), 385000 if t == 'BTC' else 490.64)
        linhas.append({'ativo': t, 'classe': cls, 'preco_unit': prc, 'qtd': q, 'total atual': q * prc})

df          = pd.DataFrame(linhas)
total_geral = df['total atual'].sum()
df['part. %'] = (df['total atual'] / total_geral) * 100
df_resumo_classe = df.groupby('classe')['total atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values('total atual', ascending=False).reset_index(drop=True)
df_ativo    = df.sort_values(by='total atual', ascending=False)

CORES_HEX = ['#084594', '#2171b5', '#4292c6', '#6baed6']

aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "simular novos aportes"])

with aba_dash:

    # cabecalho
    st.metric("patrimonio total", f"R$ {total_geral:,.2f}")
    st.markdown('---')

    # linha de graficos
    col_donut, col_barras = st.columns([1, 2])

    with col_donut:
        n   = len(df_resumo_classe)
        buf = render_donut(
            labels     = df_resumo_classe['classe'].tolist(),
            values     = df_resumo_classe['total atual'].tolist(),
            hex_colors = CORES_HEX[:n],
            bg         = '#0e1117'
        )
        st.image(buf, use_container_width=True)

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

        fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])

        fig_ativo.add_trace(
            go.Bar(
                x=df_ativo['ativo'], y=df_ativo['part. %'],
                marker_color='#1E88E5',
                hovertemplate='<b>%{x}</b><br>part.: %{y:.2f}%<extra></extra>'
            ),
            secondary_y=False
        )
        fig_ativo.add_trace(
            go.Scatter(
                x=df_ativo['ativo'], y=df_ativo['total atual'],
                mode='markers', marker=dict(color='rgba(0,0,0,0)'),
                hovertemplate='total: R$ %{y:,.2f}<extra></extra>'
            ),
            secondary_y=True
        )

        fig_ativo.update_layout(
            height=350,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            shapes=shapes,
            xaxis=dict(tickangle=45)
        )
        fig_ativo.update_yaxes(
            title_text="part. %", secondary_y=False,
            showgrid=True, gridcolor='#333', side='left',
            range=[0, y_max_pct],
            tickvals=ticks_pct, ticktext=[f'{v}%' for v in ticks_pct]
        )
        fig_ativo.update_yaxes(
            title_text="total (R$)", secondary_y=True,
            showgrid=False, side='right',
            range=[0, y_max_rs],
            tickvals=ticks_rs, ticktext=[f'R$ {v:,.0f}' for v in ticks_rs]
        )

        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    config = {
        'ativo':      st.column_config.TextColumn("ativo", alignment="center"),
        'classe':     st.column_config.TextColumn("classe", alignment="center"),
        'preco_unit': st.column_config.NumberColumn("preco unitario", format="R$ %.2f", alignment="center"),
        'qtd':        st.column_config.NumberColumn("qtd", alignment="center"),
        'total atual':st.column_config.NumberColumn("total atual", format="R$ %.2f", alignment="center"),
        'part. %':    st.column_config.NumberColumn("part. %", format="%.2f%%", alignment="center")
    }
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=config)
