import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

def get_data():
    # Dados base
    carteira = {
        'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
        'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
        'Cripto': {'BTC': 0.01492559},
        'Tesouro Direto': {'Renda+ 2050': 22.5}
    }
    # Preços fixos para evitar timeouts durante testes
    precos = {'IVVB11': 300, 'DIVO11': 120, 'PKIN11': 100, 'LFTB11': 110, 'TRXF11': 100, 'XPML11': 100, 'XPLG11': 100, 'KNRI11': 100, 'BTLG11': 100, 'BTCI11': 10, 'VGIR11': 10, 'MCCI11': 100, 'GARE11': 10, 'RZTR11': 100, 'KNCR11': 100, 'BTC': 350000, 'Renda+ 2050': 490}
    
    dados = []
    for cls, ativos in carteira.items():
        for t, q in ativos.items():
            dados.append({'Ativo': t, 'Classe': cls, 'Valor': q * precos.get(t, 100)})
    return pd.DataFrame(dados)

df = get_data()
df['Total_Geral'] = df['Valor'].sum()
df['Part'] = (df['Valor'] / df['Total_Geral']) * 100
df['Fix'] = 'Carteira'

# Gráfico Classe
df_c = df.groupby(['Fix', 'Classe'])['Valor'].sum().reset_index()
fig1 = px.bar(df_c, x='Fix', y='Valor', color='Classe', barmode='stack', color_discrete_sequence=px.colors.sequential.Blues_r)
fig1.update_layout(showlegend=True, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')

# Gráfico Ativo
fig2 = px.bar(df, x='Fix', y='Part', color='Ativo', barmode='stack', color_discrete_sequence=px.colors.sequential.Blues_r)
fig2.update_layout(showlegend=True, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')

tabs = st.tabs(["Dashboard", "Detalhe", "Aportes"])
with tabs[0]:
    c1, c2 = st.columns(2)
    c1.plotly_chart(fig1, use_container_width=True)
    c2.plotly_chart(fig2, use_container_width=True)
with tabs[1]:
    st.dataframe(df)
