import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# 1. Configuração da Página
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

# 2. Funções de Dados
def obter_precos_b3(tickers_lista):
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=7)
        precos = {t.upper(): float(dados[f"{t.upper()}.SA"]['Close'].ffill().iloc[-1]) for t in tickers_lista}
        return precos
    except: return {t.upper(): 100.0 for t in tickers_lista}

# 3. Definição da Carteira e Cálculos (Executado antes de qualquer interface)
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
df_ativo = df.sort_values(by='Total Atual', ascending=False)

# 4. Interface (Definição das abas)
aba_dash, aba_detalhe, aba_aportes = st.tabs(["dashboard", "detalhe", "Simular Novos Aportes"])

with aba_dash:
    c1, c2 = st.columns([1, 1.5])
    c1.metric("Patrimônio Total", f"R$ {total_geral:,.2f}")
    
    # Gráfico de Rosca
    fig_donut = px.pie(df_resumo_classe, values='Total Atual', names='Classe', hole=0.75, 
                       color_discrete_sequence=px.colors.sequential.Blues_r)
    fig_donut.update_traces(textinfo='percent+label', textposition='outside', sort=False)
    fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=200, showlegend=False)
    c2.plotly_chart(fig_donut, use_container_width=True)
    
    st.markdown('---')
    
    # Gráfico de Barras com Escalas Invertidas
    fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])
    fig_ativo.add_trace(go.Bar(x=df_ativo['Ativo'], y=df_ativo['Total Atual'], marker_color='#1E88E5'), secondary_y=False)
    fig_ativo.add_trace(go.Scatter(x=df_ativo['Ativo'], y=df_ativo['Part. %'], mode='markers', marker=dict(color='rgba(0,0,0,0)')), secondary_y=True)
    
    fig_ativo.update_layout(height=350, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
    fig_ativo.update_yaxes(title_text="Total (R$)", secondary_y=False, showgrid=True, gridcolor='#333', side='right')
    fig_ativo.update_yaxes(title_text="Participação (%)", secondary_y=True, showgrid=False, side='left')
    
    st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    st.dataframe(df, use_container_width=True)
