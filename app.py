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
        
        if ticker == 'BTC':
            qtd_formatada = f"{qtd:.8f}"
        elif ticker == 'Renda+ 2050':
            qtd_formatada = f"{qtd:.2f}"
        else:
            qtd_formatada = f"{int(qtd)}"
            
        linhas_tabela.append({
            'Ativo': ticker, 
            'Classe': classe, 
            'Preço Atual': preco,
            'Qtd': qtd_formatada, 
            'Total Atual': subtotal
        })

df = pd.DataFrame(linhas_tabela)
df['Part. %'] = (df['Total Atual'] / total_geral * 100) if total_geral > 0 else 0

# --- LÓGICA DE GEOMETRIA DOS GRÁFICOS ---
# Agrupa as classes e ordena de forma decrescente para a legenda lateral acompanhar
df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values(by='Total Atual', ascending=False)

# Vincula a ordem das classes aos ativos para que eles fiquem perfeitamente agrupados nos quadrantes
lista_classes_ordenada = df_resumo_classe['Classe'].tolist()
df['Ordem_Classe'] = df['Classe'].apply(lambda x: lista_classes_ordenada.index(x))
df_ativos_ordenados = df.sort_values(by=['Ordem_Classe', 'Total Atual'], ascending=[True, False])

# Ordenação padrão decrescente para a Tabela da aba Detalhe
df_tabela = df.sort_values(by='Total Atual', ascending=False)
df_tabela = df_tabela[['Ativo', 'Classe', 'Preço Atual', 'Qtd', 'Total Atual', 'Part. %']]

# 5. Interface Gráfica
aba_dash, aba_detalhe, aba_novos_aportes = st.tabs(['dashboard', 'detalhe', 'Simular Novos Aportes'])

with aba_dash:
    st.metric(label="Valor Total do Patrimônio Real", value=f"R$ {total_geral:,.2f}")
    
    # Legenda superior dinâmica em formato de pílulas (maior para o menor)
    html_legenda = "<div style='display: flex; gap: 20px; flex-wrap: wrap; margin-top: -10px; margin-bottom: 20px;'>"
    for _, row in df_resumo_classe.iterrows():
        perc = (row['Total Atual'] / total_geral * 100) if total_geral > 0 else 0
        html_legenda += f"<div style='background-color: #f0f2f6; padding: 4px 12px; border-radius: 15px; font-size: 14px; color: #31333F; font-weight: 500;'><span style='color: #666;'>{row['Classe']}:</span> {perc:.2f}%</div>"
    html_legenda += "</div>"
    st.markdown(html_legenda, unsafe_allow_html=True)
    
    st.markdown('---')
    
    col1, col2 = st.columns(2)
    with col1:
        fig_classe = px.pie(df_resumo_classe, values='Total Atual', names='Classe', title='Distribuição por Classe', hole=0.4)
        # Rotação em 180 graus com sentido horário força a maior fatia (FII) a preencher o 2º Quadrante (Superior Esquerdo)
        fig_classe.update_traces(rotation=180, direction='clockwise', textinfo='percent+label', sort=False)
        fig_classe.update_layout(legend=dict(traceorder='normal', itemsizing='constant'))
        st.plotly_chart(fig_classe, use_container_width=True)
        
    with col2:
        fig_ativo = px.pie(df_ativos_ordenados, values='Total Atual', names='Ativo', title='Distribuição por Ativo', hole=0.4)
        # Aplica a mesma simetria exata para o gráfico por ativos
        fig_ativo.update_traces(rotation=180, direction='clockwise', sort=False)
        fig_ativo.update_layout(legend=dict(traceorder='normal', itemsizing='constant'))
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    config_colunas = {
        'Ativo': st.column_config.TextColumn("Ativo", alignment="center"),
        'Classe': st.column_config.TextColumn("Classe", alignment="center"),
        'Preço Atual': st.column_config.NumberColumn("Preço Atual", format="R$ %.2f", alignment="center"),
        'Qtd': st.column_config.TextColumn("Qtd", alignment="center"), 
        'Total Atual': st.column_config.NumberColumn("Total Atual", format="R$ %.2f", alignment="center"),
        'Part. %': st.column_config.NumberColumn("Part. %", format="%.2f%%", alignment="center")
    }
        
    st.dataframe(
        df_tabela, 
        use_container_width=True, 
        hide_index=True, 
        column_config=config_colunas
    )

with aba_novos_aportes:
    st.subheader('💡 Área para planejamento futuro')
    st.info('Aqui nós vamos programar os botões para salvar as compras mês a mês no banco de dados!')
