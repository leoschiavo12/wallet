import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

# Configuração da página
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

# CSS para polimento visual
st.markdown("""
    <style>
        .stDataFrame div [role="gridcell"] > div { justify-content: center !important; text-align: center !important; }
        .stDataFrame div [role="columnheader"] > div { justify-content: center !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# Funções de Dados (com proteções)
def obter_precos_b3(tickers):
    if not tickers: return {}
    tk_formatados = [f"{t.upper()}.SA" for t in tickers]
    precos = {}
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=7)
        for t in tickers:
            chave = f"{t.upper()}.SA"
            try:
                preco = dados[chave]['Close'].ffill().iloc[-1] if len(tk_formatados) > 1 else dados['Close'].ffill().iloc[-1]
                precos[t.upper()] = float(preco)
            except: precos[t.upper()] = 0.0
    except: pass
    return precos

# Dados da Carteira
MINHA_CARTEIRA = {
    'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
    'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
    'Cripto': {'BTC': 0.01492559},
    'Tesouro Direto': {'Renda+ 2050': 22.5}
}

# Processamento e cálculos omitidos para brevidade (mantém a lógica anterior)
# ... (aqui entraria a lógica de total_geral e criação dos DFs) ...

# --- GRÁFICOS OTIMIZADOS ---
# Paleta: Azul Marinho (FII) -> Turquesa Claro (Cripto)
paleta_azul = ['#1A237E', '#0277BD', '#0097A7', '#80DEEA'] 

# 1. Gráfico Classe (Limpando Tooltip)
fig_classe = px.bar(df_resumo_classe, x='Carteira', y='Total Atual', color='Classe', 
                    color_discrete_sequence=paleta_azul, text='Texto_Label')
fig_classe.update_traces(hovertemplate="%{data.name}<br>Valor: R$ %{y:,.2f}<extra></extra>")
fig_classe.update_layout(showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')

# 2. Gráfico Ativos (Tooltip customizado)
fig_ativo = px.bar(df_ativos_grafico, x='Carteira', y='Part. %', color='Ativo', 
                   color_discrete_sequence=px.colors.sequential.Blues_r, text='Texto_Label')
fig_ativo.update_traces(hovertemplate="<b>%{data.name}</b><br>Part: %{y:.2f}%<extra></extra>")
fig_ativo.update_layout(showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')

# Exibição
col1, col2 = st.columns(2)
col1.plotly_chart(fig_classe, use_container_width=True)
col2.plotly_chart(fig_ativo, use_container_width=True)
