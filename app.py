import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# 1. Configuração e CSS para a Tabela
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

st.markdown("""
    <style>
        .stDataFrame div [role="gridcell"] > div { justify-content: center !important; text-align: center !important; }
        .stDataFrame div [role="columnheader"] > div { justify-content: center !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. Funções de Busca
def obter_precos_b3(tickers_lista):
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=7)
        return {t.upper(): float(dados[f"{t.upper()}.SA"]['Close'].ffill().iloc[-1]) for t in tickers_lista}
    except:
        return {t.upper(): 100.0 for t in tickers_lista}

# 3. Dados
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
        linhas.append({'Ativo': t, 'Classe': cls, 'Preço': prc, 'Qtd': q, 'Total Atual': q * prc})

df = pd.DataFrame(linhas)
total_geral = df['Total Atual'].sum()
df['Part. %'] = (df['Total Atual'] / total_geral) * 100
df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()
df_ativo = df.sort_values(by='Total Atual', ascending=False)

# 4. Interface
aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "Simular Novos Aportes"])

with aba_dash:
    st.metric("Patrimonio Total", f"R$ {total_geral:,.2f}")
    st.markdown('---')

    col_donut, col_barras = st.columns([1, 2])

    with col_donut:
        fig_donut = go.Figure(go.Pie(
            labels=df_resumo_classe['Classe'].tolist(),
            values=df_resumo_classe['Total Atual'].tolist(),
            hole=0.75,
            textinfo='percent+label',
            textposition='outside',
            marker=dict(colors=px.colors.sequential.Blues_r[:len(df_resumo_classe)])
        ))
        fig_donut.update_layout(margin=dict(t=40, b=40, l=40, r=40), height=350, showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_barras:
        fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ativo.add_trace(go.Bar(x=df_ativo['Ativo'], y=df_ativo['Total Atual'], marker_color='#1E88E5'), secondary_y=False)
        fig_ativo.add_trace(go.Scatter(x=df_ativo['Ativo'], y=df_ativo['Part. %'], mode='markers', marker=dict(color='rgba(0,0,0,0)')), secondary_y=True)
        fig_ativo.update_layout(height=350, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
        fig_ativo.update_yaxes(title_text="Total (R$)", secondary_y=False, showgrid=True, gridcolor='#333', side='right')
        fig_ativo.update_yaxes(title_text="Participacao (%)", secondary_y=True, showgrid=False, side='left')
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    config = {
        'Ativo': st.column_config.TextColumn("Ativo", alignment="center"),
        'Classe': st.column_config.TextColumn("Classe", alignment="center"),
        'Preço': st.column_config.NumberColumn("Preço", format="R$ %.2f", alignment="center"),
        'Qtd': st.column_config.NumberColumn("Qtd", alignment="center"),
        'Total Atual': st.column_config.NumberColumn("Total Atual", format="R$ %.2f", alignment="center"),
        'Part. %': st.column_config.NumberColumn("Part. %", format="%.2f%%", alignment="center")
    }
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=config)
