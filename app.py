import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="")

def obter_precos_b3(tickers_lista):
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=7)
        precos = {t.upper(): float(dados[f"{t.upper()}.SA"]['Close'].ffill().iloc[-1]) for t in tickers_lista}
        return precos
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
        linhas.append({'Ativo': t, 'Classe': cls, 'Total Atual': q * prc})

df = pd.DataFrame(linhas)
total_geral = df['Total Atual'].sum()
df['Part. %'] = (df['Total Atual'] / total_geral) * 100
df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values('Total Atual', ascending=False).reset_index(drop=True)
df_ativo = df.sort_values(by='Total Atual', ascending=False)

aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "Simular Novos Aportes"])

with aba_dash:
    st.metric("Patrimonio Total", f"R$ {total_geral:,.2f}")
    st.markdown('---')

    col_donut, col_barras = st.columns([1, 2])

    with col_donut:
        # O Plotly com counterclockwise ignora o rotation de forma nao intuitiva.
        # Solucao: usar clockwise (padrao) e calcular o rotation para que
        # a borda DIREITA do FII fique no topo (90 graus no sistema Plotly onde 0=direita).
        # Com clockwise, rotation=X coloca o inicio do 1o segmento em X graus (0=direita, 90=topo).
        # Queremos FII comecando no topo = rotation=90, sentido horario...
        # MAS queremos anti-horario visualmente.
        # Truque: inverter a ordem dos dados e usar clockwise.
        # Assim visualmente parece anti-horario com FII comecando no topo.

        df_inv = df_resumo_classe.iloc[::-1].reset_index(drop=True)

        # Com clockwise e rotation=90, o ultimo item da lista original (Cripto) comecaria no topo.
        # Precisamos que FII (maior) fique no topo.
        # Calculamos onde Cripto terminaria para FII comecar la.
        total_exc_fii = df_inv['Total Atual'].iloc[:-1].sum()
        pct_exc_fii = total_exc_fii / df_inv['Total Atual'].sum()
        rotation_val = 90 + pct_exc_fii * 360

        fig_donut = go.Figure(go.Pie(
            labels=df_inv['Classe'].tolist(),
            values=df_inv['Total Atual'].tolist(),
            hole=0.75,
            rotation=rotation_val,
            direction='clockwise',
            sort=False,
            textinfo='percent+label',
            textposition='outside',
            marker=dict(colors=list(reversed(px.colors.sequential.Blues_r[:len(df_resumo_classe)])))
        ))
        fig_donut.update_layout(
            margin=dict(t=60, b=60, l=60, r=60),
            height=350,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_barras:
        fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ativo.add_trace(
            go.Bar(x=df_ativo['Ativo'], y=df_ativo['Total Atual'], marker_color='#1E88E5'),
            secondary_y=False
        )
        fig_ativo.add_trace(
            go.Scatter(x=df_ativo['Ativo'], y=df_ativo['Part. %'], mode='markers', marker=dict(color='rgba(0,0,0,0)')),
            secondary_y=True
        )
        fig_ativo.update_layout(
            height=350,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False
        )
        fig_ativo.update_yaxes(title_text="Total (R$)", secondary_y=False, showgrid=True, gridcolor='#333', side='right')
        fig_ativo.update_yaxes(title_text="Participacao (%)", secondary_y=True, showgrid=False, side='left')
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    st.dataframe(df, use_container_width=True)
