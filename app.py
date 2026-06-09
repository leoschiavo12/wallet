import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# 1. Configuração e CSS
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

st.markdown("""
    <style>
        .stDataFrame div [role="gridcell"] > div { justify-content: center !important; text-align: center !important; }
        .stDataFrame div [role="columnheader"] > div { justify-content: center !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. Funções
def obter_precos_b3(tickers_lista):
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=7)
        return {t.upper(): float(dados[f"{t.upper()}.SA"]['Close'].ffill().iloc[-1]) for t in tickers_lista}
    except: return {t.upper(): 100.0 for t in tickers_lista}

def obter_preco_btc():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-BRL/spot", timeout=4)
        return float(res.json()['data']['amount'])
    except: return 385000.00

# 3. Processamento
MINHA_CARTEIRA = {
    'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
    'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
    'Cripto': {'BTC': 0.01492559},
    'Tesouro Direto': {'Renda+ 2050': 22.5}
}

todos_b3 = [t for cls in ['ETF', 'FII'] for t in MINHA_CARTEIRA[cls].keys()]
precos = obter_precos_b3(todos_b3)
prc_btc = obter_preco_btc()

linhas = []
for cls, ativos in MINHA_CARTEIRA.items():
    for t, q in ativos.items():
        prc = prc_btc if t == 'BTC' else (precos.get(t.upper(), 100.0) if cls in ['ETF', 'FII'] else 490.64)
        linhas.append({'Ativo': t, 'Classe': cls, 'Total Atual': q * prc})

df = pd.DataFrame(linhas)
total_geral = df['Total Atual'].sum()
df['Part. %'] = (df['Total Atual'] / total_geral) * 100
df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()
df_ativo = df.sort_values(by='Total Atual', ascending=False)

# 4. Interface
aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "Simular Novos Aportes"])

with aba_dash:
    st.metric("Patrimônio Total", f"R$ {total_geral:,.2f}")
    st.markdown('---')
    
    col1, col2 = st.columns([1, 1.5])
    
    with col1:
        fig_donut = px.pie(df_resumo_classe, values='Total Atual', names='Classe', hole=0.75, 
                           color_discrete_sequence=px.colors.sequential.Blues_r)
        fig_donut.update_traces(textinfo='percent+label', textposition='outside', sort=False,
                               hovertemplate="<b>%{label}</b><br>R$ %{value:,.2f}<br>%{percent:.1%}<extra></extra>")
        fig_donut.update_layout(margin=dict(t=20, b=20, l=20, r=20), height=300, showlegend=False)
        st.plotly_chart(fig_donut, use_container_width=True)
    
    with col2:
        fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])
        fig_ativo.add_trace(go.Bar(x=df_ativo['Ativo'], y=df_ativo['Total Atual'], marker_color='#1E88E5',
                                  hovertemplate="<b>%{x}</b><br>R$ %{y:,.2f}<extra></extra>"), secondary_y=False)
        fig_ativo.add_trace(go.Scatter(x=df_ativo['Ativo'], y=df_ativo['Part. %'], mode='markers', marker=dict(color='rgba(0,0,0,0)'),
                                      hovertemplate="%{y:.1f}%<extra></extra>"), secondary_y=True)
        fig_ativo.update_layout(height=300, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
        fig_ativo.update_yaxes(title_text="Total (R$)", secondary_y=False, side='right')
        fig_ativo.update_yaxes(title_text="Part. (%)", secondary_y=True, side='left')
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    config = {'Ativo': st.column_config.TextColumn("Ativo", alignment="center"),
              'Classe': st.column_config.TextColumn("Classe", alignment="center"),
              'Preço': st.column_config.NumberColumn("Preço", format="R$ %.2f", alignment="center"),
              'Qtd': st.column_config.NumberColumn("Qtd", alignment="center"),
              'Total Atual': st.column_config.NumberColumn("Total Atual", format="R$ %.2f", alignment="center"),
              'Part. %': st.column_config.NumberColumn("Part. %", format="%.2f%%", alignment="center")}
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=config)
