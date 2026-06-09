import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

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
df_ativo = df.sort_values(by='total atual', ascending=False)

aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "simular novos aportes"])

with aba_dash:

    # linha superior: patrimonio + donut + grafico de barras
    col_metric_donut, col_barras = st.columns([1, 2])

    with col_metric_donut:
        st.metric("patrimonio total", f"R$ {total_geral:,.2f}")

        fig_donut = go.Figure(go.Pie(
            labels=df_resumo_classe['classe'].tolist(),
            values=df_resumo_classe['total atual'].tolist(),
            hole=0.72,
            textinfo='percent+label',
            textposition='outside',
            textfont=dict(size=11),
            marker=dict(colors=px.colors.sequential.Blues_r[:len(df_resumo_classe)])
        ))
        fig_donut.update_layout(
            margin=dict(t=30, b=30, l=30, r=30),
            height=260,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_barras:
        # escala direita (total R$) dinamica: 40% do patrimonio total
        y_max_pct = 40
        y_max_rs = total_geral * y_max_pct / 100

        # linhas de referencia em 5%, 15%, 25%, 35% convertidas para R$
        sub_escalas_pct = [5, 15, 25, 35]
        sub_escalas_rs  = [total_geral * p / 100 for p in sub_escalas_pct]

        fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])

        fig_ativo.add_trace(
            go.Bar(
                x=df_ativo['ativo'],
                y=df_ativo['total atual'],
                marker_color='#1E88E5',
                hovertemplate='<b>%{x}</b><br>total: R$ %{y:,.2f}<extra></extra>'
            ),
            secondary_y=False
        )

        # eixo secundario invisivel apenas para mostrar % no hover
        fig_ativo.add_trace(
            go.Scatter(
                x=df_ativo['ativo'],
                y=df_ativo['part. %'],
                mode='markers',
                marker=dict(color='rgba(0,0,0,0)'),
                hovertemplate='part.: %{y:.2f}%<extra></extra>'
            ),
            secondary_y=True
        )

        # linhas de sub-escala em 5, 15, 25, 35%
        shapes = []
        for rs_val in sub_escalas_rs:
            shapes.append(dict(
                type='line',
                xref='paper', x0=0, x1=1,
                yref='y', y0=rs_val, y1=rs_val,
                line=dict(color='rgba(255,255,255,0.12)', width=1, dash='dot')
            ))

        fig_ativo.update_layout(
            height=350,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            shapes=shapes
        )

        # eixo esquerdo: total R$, escala fixa ate 40% do patrimonio
        fig_ativo.update_yaxes(
            title_text="total (R$)",
            secondary_y=False,
            showgrid=True,
            gridcolor='#333',
            side='left',
            range=[0, y_max_rs],
            tickvals=[total_geral * p / 100 for p in [0, 10, 20, 30, 40]],
            ticktext=['0', '10k' if total_geral * 0.1 < 1e6 else '100k',
                      f'R${total_geral*0.2:,.0f}', f'R${total_geral*0.3:,.0f}', f'R${total_geral*0.4:,.0f}']
        )

        # eixo direito: participacao %, escala fixa 0-40%
        fig_ativo.update_yaxes(
            title_text="part. %",
            secondary_y=True,
            showgrid=False,
            side='right',
            range=[0, y_max_pct],
            tickvals=[0, 10, 20, 30, 40],
            ticktext=['0%', '10%', '20%', '30%', '40%']
        )

        st.plotly_chart(fig_ativo, use_container_width=True)

    st.markdown('---')

with aba_detalhe:
    config = {
        'ativo': st.column_config.TextColumn("ativo", alignment="center"),
        'classe': st.column_config.TextColumn("classe", alignment="center"),
        'preco_unit': st.column_config.NumberColumn("preco unitario", format="R$ %.2f", alignment="center"),
        'qtd': st.column_config.NumberColumn("qtd", alignment="center"),
        'total atual': st.column_config.NumberColumn("total atual", format="R$ %.2f", alignment="center"),
        'part. %': st.column_config.NumberColumn("part. %", format="%.2f%%", alignment="center")
    }
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=config)
