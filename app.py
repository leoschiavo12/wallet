import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

# 1. Configuração da Página
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

# 2. Funções de Busca de Preços
def obter_precos_b3(tickers_lista):
    if not tickers_lista: return {}
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
            except: precos[t.upper()] = 0.0
    except: pass
    return precos

def obter_preco_btc():
    try:
        res = requests.get("https://api.coinbase.com/v2/prices/BTC-BRL/spot", timeout=5)
        return float(res.json()['data']['amount'])
    except: return 0.0

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
for c, ativos in MINHA_CARTEIRA.items():
    if c in ['ETF', 'FII']: todos_b3.extend(ativos.keys())

bancada_precos = obter_precos_b3(todos_b3)
preco_btc = obter_preco_btc()
preco_tesouro = obter_preco_renda_2050()

linhas_tabela = []
total_geral = 0.0

for classe, ativos in MINHA_CARTEIRA.items():
    for ticker, qtd in ativos.items():
        if classe in ['ETF', 'FII']: 
            preco = bancada_precos.get(ticker.upper(), 0.0)
        elif ticker == 'BTC': 
            preco = preco_btc
        else: 
            preco = preco_tesouro
        
        subtotal = qtd * preco
        total_geral += subtotal
        linhas_tabela.append({
            'Ativo': ticker, 
            'Classe': classe, 
            'Quantidade': qtd, 
            'Preço Atual': preco, 
            'Total Atual': subtotal
        })

df = pd.DataFrame(linhas_tabela)
# Ajuste no cálculo da participação (multiplicado por 100)
df['Participação'] = (df['Total Atual'] / total_geral * 100) if total_geral > 0 else 0

# 5. Interface Gráfica
aba_dash, aba_detalhe, aba_novos_aportes = st.tabs(['dashboard', 'detalhe', 'Simular Novos Aportes'])

with aba_dash:
    st.metric(label="Valor Total do Patrimônio Real", value=f"R$ {total_geral:,.2f}")
    
    # Resumo Percentual (Pílulas)
    df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()
    df_resumo_classe['%'] = (df_resumo_classe['Total Atual'] / total_geral * 100) if total_geral > 0 else 0
    df_resumo_classe = df_resumo_classe.sort_values(by='%', ascending=False)
    
    html_legenda = "<div style='display: flex; gap: 20px; flex-wrap: wrap; margin-top: -10px; margin-bottom: 20px;'>"
    for _, row in df_resumo_classe.iterrows():
        html_legenda += f"<div style='background-color: #f0f2f6; padding: 4px 12px; border-radius: 15px; font-size: 14px; color: #31333F; font-weight: 500;'><span style='color: #666;'>{row['Classe']}:</span> {row['%']:.2f}%</div>"
    html_legenda += "</div>"
    st.markdown(html_legenda, unsafe_allow_html=True)
    
    st.markdown('---')
    
    col1, col2 = st.columns(2)
    with col1:
        fig_classe = px.pie(df, values='Total Atual', names='Classe', title='Distribuição por Classe', hole=0.4)
        # Rotação 0 + sentido anti-horário joga o início para o 2º quadrante (esquerda superior)
        fig_classe.update_traces(rotation=0, direction='counterclockwise', textinfo='percent+label')
        st.plotly_chart(fig_classe, use_container_width=True)
    with col2:
        fig_ativo = px.pie(df, values='Total Atual', names='Ativo', title='Distribuição por Ativo', hole=0.4)
        fig_ativo.update_traces(rotation=0, direction='counterclockwise')
        fig_ativo.update_layout(legend=dict(traceorder='normal', itemsizing='constant'))
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    st.subheader('📋 Detalhamento Fino da Carteira')
    
    # Configuração de Colunas com Centralização e Formatação
    config_colunas = {
        'Ativo': st.column_config.TextColumn("Ativo", width="medium", help="Código do ativo", validate=None),
        'Classe': st.column_config.TextColumn("Classe"),
        'Quantidade': st.column_config.NumberColumn("Qtd", format="%.2f"),
        'Preço Atual': st.column_config.NumberColumn("Preço Atual", format="R$ %.2f"),
        'Total Atual': st.column_config.NumberColumn("Total Atual", format="R$ %.2f"),
        'Participação': st.column_config.NumberColumn("Part. %", format="%.2f%%")
    }
    
    # Exibição do Dataframe (A centralização é aplicada via CSS injetado para garantir eficácia)
    st.markdown("""
        <style>
            div[data-testid="stDataFrame"] td {text-align: center !important;}
            div[data-testid="stDataFrame"] th {text-align: center !important;}
        </style>
        """, unsafe_allow_html=True)
        
    st.dataframe(df, use_container_width=True, hide_index=True, column_config=config_colunas)

with aba_novos_aportes:
    st.subheader('💡 Área para planejamento futuro')
    st.info('Aqui nós vamos programar os botões para salvar as compras mês a mês no banco de dados!')
