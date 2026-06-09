import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

# 1. Configuração da Página
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

# 2. Funções de Dados (Protegidas)
def obter_precos_b3(tickers_lista):
    if not tickers_lista: return {}
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    precos = {}
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=10)
        for t in tickers_lista:
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
todos_b3 = [t for cls in ['ETF', 'FII'] for t in MINHA_CARTEIRA[cls].keys()]
bancada = obter_precos_b3(todos_b3)
linhas = []
total_geral = 0.0

for cls, ativos in MINHA_CARTEIRA.items():
    for t, q in ativos.items():
        preco = bancada.get(t.upper(), 0.0) if cls in ['ETF', 'FII'] else (385000.0 if t == 'BTC' else 490.64)
        subtotal = q * preco
        total_geral += subtotal
        linhas.append({'Ativo': t, 'Classe': cls, 'Total': subtotal, 'Carteira': 'Total'})

df = pd.DataFrame(linhas)
df['Part'] = (df['Total'] / total_geral) * 100

# 5. Gráficos (Paleta de Azuis e Limpeza)
paleta_azul = ['#1A237E', '#0277BD', '#0097A7', '#80DEEA']

fig_classe = px.bar(df.groupby('Classe')['Total'].sum().reset_index(), x=['Total']*4, y='Total', color='Classe', barmode='stack', color_discrete_sequence=paleta_azul)
fig_classe.update_traces(hovertemplate="<b>%{data.name}</b><br>R$ %{y:,.2f}<extra></extra>")
fig_classe.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=True)

fig_ativo = px.bar(df, x='Carteira', y='Part', color='Ativo', barmode='stack', color_discrete_sequence=px.colors.sequential.Blues_r)
fig_ativo.update_traces(hovertemplate="<b>%{data.name}</b><br>Part: %{y:.2f}%<extra></extra>")
fig_ativo.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=True)

# 6. Interface
aba1, aba2, aba3 = st.tabs(["Dashboard", "Detalhe", "Simular Novos Aportes"])
with aba1:
    col1, col2 = st.columns(2)
    col1.plotly_chart(fig_classe, use_container_width=True)
    col2.plotly_chart(fig_ativo, use_container_width=True)
with aba2:
    st.dataframe(df)
