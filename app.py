import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

# 1. Configuração da Página
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

# 2. Funções de Dados
def obter_precos_b3(tickers):
    if not tickers: return {}
    tk_formatados = [f"{t.upper()}.SA" for t in tickers]
    precos = {}
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=10)
        for t in tickers:
            chave = f"{t.upper()}.SA"
            try:
                preco = dados[chave]['Close'].ffill().iloc[-1] if len(tk_formatados) > 1 else dados['Close'].ffill().iloc[-1]
                precos[t.upper()] = float(preco)
            except: precos[t.upper()] = 0.0
    except: pass
    return precos

# 3. Dados da Carteira
MINHA_CARTEIRA = {
    'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
    'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
    'Cripto': {'BTC': 0.01492559},
    'Tesouro Direto': {'Renda+ 2050': 22.5}
}

# 4. Processamento
todos_b3 = [t for classe in ['ETF', 'FII'] for t in MINHA_CARTEIRA[classe].keys()]
bancada = obter_precos_b3(todos_b3)
total_geral = 0.0
linhas = []

for classe, ativos in MINHA_CARTEIRA.items():
    for ticker, qtd in ativos.items():
        preco = bancada.get(ticker.upper(), 0.0) if classe in ['ETF', 'FII'] else (385000.0 if ticker == 'BTC' else 490.64)
        subtotal = qtd * preco
        total_geral += subtotal
        linhas.append({'Ativo': ticker, 'Classe': classe, 'Total': subtotal})

df = pd.DataFrame(linhas)
df['Part'] = (df['Total'] / total_geral) * 100
df_classe = df.groupby('Classe')['Total'].sum().reset_index()
df_classe['Carteira'] = 'Minha Carteira' # Necessário para empilhamento no Plotly

# 5. Gráficos (Paleta Azul: Escuro para Claro)
paleta_azul = ['#1A237E', '#0277BD', '#0097A7', '#80DEEA'] 

# Gráfico de Classes (Empilhado)
fig_classe = px.bar(df_classe, x='Carteira', y='Total', color='Classe', 
                    color_discrete_sequence=paleta_azul, barmode='stack')
fig_classe.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=True)

# Gráfico de Ativos (Empilhado)
fig_ativo = px.bar(df, x='Carteira', y='Part', color='Ativo', 
                   color_discrete_sequence=px.colors.sequential.Blues_r, barmode='stack')
fig_ativo.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=True)

# 6. Interface (Abas corrigidas)
aba_dash, aba_detalhe, aba_aportes = st.tabs(["Dashboard", "Detalhe", "Simular Novos Aportes"])

with aba_dash:
    st.subheader("Visão Geral")
    col1, col2 = st.columns(2)
    col1.plotly_chart(fig_classe, use_container_width=True)
    col2.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    st.dataframe(df)

with aba_aportes:
    st.write("Funcionalidade em construção.")
