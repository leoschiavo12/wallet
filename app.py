import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

# 1. Configuração da Página
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

# Injeção de CSS para centralização de tabelas
st.markdown("""
    <style>
        .stDataFrame div [role="gridcell"] > div { justify-content: center !important; text-align: center !important; }
        .stDataFrame div [role="columnheader"] > div { justify-content: center !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. Funções de Busca
def obter_precos_b3(tickers_lista):
    if not tickers_lista: return {}
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    precos = {}
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=7)
        for t in tickers_lista:
            chave = f"{t.upper()}.SA"
            try:
                if len(tk_formatados) > 1: preco = dados[chave]['Close'].ffill().iloc[-1]
                else: preco = dados['Close'].ffill().iloc[-1]
                precos[t.upper()] = float(preco) if str(preco) != 'nan' else 0.0
            except: precos[t.upper()] = 0.0
    except: pass
    return precos

def obter_preco_btc():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-BRL/spot", timeout=4)
        return float(res.json()['data']['amount'])
    except: return 385000.00

# 3. Dados
MINHA_CARTEIRA = {
    'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
    'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
    'Cripto': {'BTC': 0.01492559},
    'Tesouro Direto': {'Renda+ 2050': 22.5}
}

todos_b3 = [t for cls in ['ETF', 'FII'] for t in MINHA_CARTEIRA[cls].keys()]
bancada_precos = obter_precos_b3(todos_b3)
total_geral = 0.0
linhas_tabela = []

for classe, ativos in MINHA_CARTEIRA.items():
    for ticker, qtd in ativos.items():
        preco = bancada_precos.get(ticker.upper(), 100.0) if classe in ['ETF', 'FII'] else (obter_preco_btc() if ticker == 'BTC' else 490.64)
        subtotal = qtd * preco
        total_geral += subtotal
        linhas_tabela.append({'Ativo': ticker, 'Classe': classe, 'Preço Atual': preco, 'Qtd': qtd, 'Total Atual': subtotal})

df = pd.DataFrame(linhas_tabela)
df['Part. %'] = (df['Total Atual'] / total_geral * 100)
df['Carteira'] = ''

cores_classe = {'FII': '#3A6B68', 'Tesouro Direto': '#5F8D75', 'ETF': '#B86B5C', 'Cripto': '#D4A35D'}
df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()

# 4. Interface Gráfica
aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "Simular Novos Aportes"])

with aba_dash:
    # Cabeçalho com métrica e gráfico de rosca
    c1, c2 = st.columns([1, 2])
    c1.metric("Patrimônio Total", f"R$ {total_geral:,.2f}")
    
    fig_donut = px.pie(df_resumo_classe, values='Total Atual', names='Classe', hole=0.6, color='Classe', color_discrete_map=cores_classe)
    fig_donut.update_traces(textinfo='percent+label')
    fig_donut.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=180, showlegend=False)
    c2.plotly_chart(fig_donut, use_container_width=True)
    
    st.markdown('---')
    
    # Gráficos de barras mantidos
    col1, col2 = st.columns(2)
    with col1:
        fig_classe = px.bar(df_resumo_classe, x='Classe', y='Total Atual', color='Classe', color_discrete_map=cores_classe, barmode='stack')
        st.plotly_chart(fig_classe, use_container_width=True)
    with col2:
        fig_ativo = px.bar(df, x='Ativo', y='Part. %', color='Ativo', barmode='stack')
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    st.dataframe(df, use_container_width=True)

with aba_aportes:
    st.info('Área de simulação em desenvolvimento.')
