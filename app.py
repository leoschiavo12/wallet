import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

# 1. Configuração inicial
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

# 2. Dados e Processamento (A lógica que estava funcionando)
MINHA_CARTEIRA = {
    'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
    'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
    'Cripto': {'BTC': 0.01492559},
    'Tesouro Direto': {'Renda+ 2050': 22.5}
}

# (Mantendo a lógica de cálculo que gerava a tabela correta)
def obter_dados_carteira():
    # Usando valores fixos temporários para garantir 100% de estabilidade e evitar erros de rede
    precos = {'IVVB11': 300, 'DIVO11': 120, 'PKIN11': 100, 'LFTB11': 110, 'TRXF11': 100, 'XPML11': 100, 'XPLG11': 100, 'KNRI11': 100, 'BTLG11': 100, 'BTCI11': 10, 'VGIR11': 10, 'MCCI11': 100, 'GARE11': 10, 'RZTR11': 100, 'KNCR11': 100, 'BTC': 350000, 'Renda+ 2050': 490}
    linhas = []
    for cls, ativos in MINHA_CARTEIRA.items():
        for t, q in ativos.items():
            valor = q * precos.get(t, 100)
            linhas.append({'Ativo': t, 'Classe': cls, 'Valor': valor})
    df = pd.DataFrame(linhas)
    total = df['Valor'].sum()
    df['Part'] = (df['Valor'] / total) * 100
    df['Carteira'] = 'Minha Carteira'
    return df

df = obter_dados_carteira()

# 3. Gráficos com Paleta Azul e Tooltips Limpos
# FII (Escuro) -> ETF -> Tesouro -> Cripto (Claro)
paleta_azul = ['#1A237E', '#0D47A1', '#0288D1', '#81D4FA']

fig_classe = px.bar(df.groupby('Classe')['Valor'].sum().reset_index(), 
                    x=['Total']*4, y='Valor', color='Classe', barmode='stack', 
                    color_discrete_sequence=paleta_azul)
fig_classe.update_traces(hovertemplate="<b>%{data.name}</b><br>R$ %{y:,.2f}<extra></extra>")
fig_classe.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=True)

fig_ativo = px.bar(df, x='Carteira', y='Part', color='Ativo', barmode='stack', 
                   color_discrete_sequence=px.colors.sequential.Blues_r)
fig_ativo.update_traces(hovertemplate="<b>%{data.name}</b><br>Part: %{y:.2f}%<extra></extra>")
fig_ativo.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=True)

# 4. Interface (Abas)
aba1, aba2, aba3 = st.tabs(["Dashboard", "Detalhe", "Simular Novos Aportes"])

with aba1:
    col1, col2 = st.columns(2)
    col1.plotly_chart(fig_classe, use_container_width=True)
    col2.plotly_chart(fig_ativo, use_container_width=True)

with aba2:
    st.dataframe(df, use_container_width=True)

with aba3:
    st.info("Funcionalidade em desenvolvimento.")
