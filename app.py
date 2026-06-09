import streamlit as st
import plotly.express as px
import pandas as pd

# 1. Configuração inicial
st.set_page_config(page_title="SmartWallet", layout="wide")

# 2. Dados (Estratégia de preços fixos para garantir estabilidade)
def get_data():
    carteira = {
        'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
        'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
        'Cripto': {'BTC': 0.01492559},
        'Tesouro Direto': {'Renda+ 2050': 22.5}
    }
    precos = {'IVVB11': 300, 'DIVO11': 120, 'PKIN11': 100, 'LFTB11': 110, 'TRXF11': 100, 'XPML11': 100, 'XPLG11': 100, 'KNRI11': 100, 'BTLG11': 100, 'BTCI11': 10, 'VGIR11': 10, 'MCCI11': 100, 'GARE11': 10, 'RZTR11': 100, 'KNCR11': 100, 'BTC': 350000, 'Renda+ 2050': 490}
    dados = [{'Ativo': t, 'Classe': cls, 'Valor': q * precos.get(t, 100)} for cls, ativos in carteira.items() for t, q in ativos.items()]
    df = pd.DataFrame(dados)
    df['Part'] = (df['Valor'] / df['Valor'].sum()) * 100
    df['Fix'] = 'Total'
    return df

df = get_data()

# 3. Gráficos
# Paleta Azul do Escuro para Claro
azul_seq = ['#1A237E', '#0277BD', '#0097A7', '#80DEEA']

fig1 = px.bar(df.groupby(['Fix', 'Classe'])['Valor'].sum().reset_index(), 
              x='Fix', y='Valor', color='Classe', barmode='stack', 
              color_discrete_sequence=azul_seq)
fig1.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=True)

fig2 = px.bar(df, x='Fix', y='Part', color='Ativo', barmode='stack', 
              color_discrete_sequence=px.colors.sequential.Blues_r)
fig2.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=True)

# 4. Interface (Abas)
tabs = st.tabs(["Dashboard", "Detalhe", "Aportes"])
with tabs[0]:
    c1, c2 = st.columns(2)
    c1.plotly_chart(fig1, use_container_width=True)
    c2.plotly_chart(fig2, use_container_width=True)
with tabs[1]:
    st.dataframe(df)
with tabs[2]:
    st.write("Em construção.")
