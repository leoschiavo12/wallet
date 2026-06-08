import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

# 1. Configuração da Página
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

# Injeção de CSS para garantir a centralização da tabela nativa do Streamlit
st.markdown("""
    <style>
        .stDataFrame div [role="gridcell"] > div {
            justify-content: center !important;
            text-align: center !important;
        }
        .stDataFrame div [role="columnheader"] > div {
            justify-content: center !important;
            text-align: center !important;
        }
    </style>
    """, unsafe_allow_html=True)

# 2. Funções de Busca de Preços
def obter_precos_b3(tickers_lista):
    if not tickers_lista:
        return {}
    tickers_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    precos = {}
    try:
        dados = yf.download(tickers_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True)
        for t in tickers_lista:
            chave = f"{t.upper()}.SA"
            try:
                if len(tickers_formatados) > 1:
                    preco = dados[chave]['Close'].ffill().iloc[-1]
                else:
                    preco = dados['Close'].ffill().iloc[-1]
                precos[t.upper()] = float(preco) if str(preco) != 'nan' else 0.0
            except:
                precos[t.upper()] = 0.0
    except:
        pass
    return precos

def obter_preco_btc():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-BRL/spot", timeout=5)
        return float(res.json()['data']['amount'])
    except:
        return 0.0

def obter_preco_renda_2050():
    return 490.64

# 3. Dados da Carteira
MINHA_CARTEIRA = {
    'ETF': {
        'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30
    },
    'FII': {
        'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4,
        'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10,
        'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2
    },
    'Cripto': {
        'BTC': 0.01492559
    },
    'Tesouro Direto': {
        'Renda+ 2050': 22.5
    }
}

# 4. Processamento de Dados
todos_b3 = []
for classe_nome, ativos in MINHA_CARTEIRA.items():
    if classe_nome in ['ETF', 'FII']:
        todos_b3.extend(ativos.keys())

bancada_precos = obter_precos_b3(todos_b3)
preco_btc = obter_preco_btc()
preco_tesouro = obter_preco_renda_2050()

linhas_tabela = []
total_geral = 0.0

# Indentação corrigida e alinhada estritamente com 4 espaços
for classe, ativos in MINHA_CARTEIRA.items():
    for ticker, qtd in ativos.items():
        if classe in ['ETF', 'FII']: 
            preco = bancada_precos.get(
