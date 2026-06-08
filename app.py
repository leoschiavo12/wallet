import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

# 1. Configuração da Página
st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="📊")

# Forçar o alinhamento centralizado de todas as células usando markdown global
st.markdown("""
    <style>
        div[data-testid="stDataFrame"] td, 
        div[data-testid="stDataFrame"] th,
        .stDataFrame iframe,
        div[data-grid-canvas] {
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
        
        linhas_tabela.append({
            'Ativo': ticker, 
            'Classe': classe, 
            'Preço Numérico': preco,
            'Qtd Numérica': qtd,
            'Total Numérico': subtotal
        })

df_base = pd.DataFrame(linhas_tabela)
df_base['Part. % Numérica'] = (df_base['Total Numérico'] / total_geral * 100) if total_geral > 0 else 0

# Ordenação padrão pelo maior patrimônio
df_base = df_base.sort_values(by='Total Numérico', ascending=False)

# Criando a tabela final com os textos pré-formatados para FORÇAR a centralização
df_exibicao = pd.DataFrame()
df_exibicao['Ativo'] = df_base['Ativo']
df_exibicao['Classe'] = df_base['Classe']
df_exibicao['Preço Atual'] = df_base['Preço Numérico'].map('R$ {:.2f}'.format)

# Tratamento das regras de casas decimais para Qtd
qtd_formatada = []
for idx, row in df_base.iterrows():
    if row['Ativo'] == 'BTC':
        qtd_formatada.append(f"{row['Qtd Numérica']:.8f}")
    elif row['Ativo'] == 'Renda+ 2050':
        qtd_formatada.append(f"{row['Qtd Numérica']:.2f}")
    else:
        qtd_formatada.append(f"{int(row['Qtd Numérica'])}")
df_exibicao['Qtd'] = qtd_formatada

df_exibicao['Total Atual'] = df_base['Total Numérico'].map('R$ {:.2f}'.format)
df_exibicao['Part. %'] = df_base['Part. % Numérica'].map('{:.2f}%'.format)

# 5. Interface Gráfica
aba_dash, aba_detalhe, aba_novos_aportes = st.tabs(['dashboard', 'detalhe', 'Simular Novos Aportes'])

with aba_dash:
    st.metric(label="Valor Total do Patrimônio Real", value=f"R$ {total_geral:,.2f}")
    
    # Resumo Percentual (Pílulas)
    df_resumo_classe = df_base.groupby('Classe')['Total Numérico'].sum().reset_index()
    df_resumo_classe['%'] = (df_resumo_classe['Total Numérico'] / total_geral * 100) if total_geral > 0 else 0
    df_resumo_classe = df_resumo_classe.sort_values(by='%', ascending=False)
    
    html_legenda = "<div style='display: flex; gap: 20px; flex-wrap: wrap; margin-top: -10px; margin-bottom: 20px;'>"
    for _, row in df_resumo_classe.iterrows():
        html_legenda += f"<div style='background-color: #f0f2f6; padding: 4px 12px; border-radius: 15px; font-size: 14px; color: #31333F; font-weight: 500;'><span style='color: #666;'>{row['Classe']}:</span> {row['%']:.2f}%</div>"
    html_legenda += "</div>"
    st.markdown(html_legenda, unsafe_allow_html=True)
    
    st.markdown('---')
    
    col1, col2 = st.columns(2)
    with col1:
        # Gráfico por Classe ordenado explicitamente do maior para o menor
        fig_classe = px.pie(df_resumo_classe, values='Total Numérico', names='Classe', title='Distribuição por Classe', hole=0.4)
        fig_classe.update_traces(rotation=90, direction='counterclockwise', textinfo='percent+label')
        st.plotly_chart(fig_classe, use_container_width=True)
    with col2:
        # Gráfico por Ativo ordenado explicitamente do maior para o menor
        fig_ativo = px.pie(df_base, values='Total Numérico', names='Ativo', title='Distribuição por Ativo', hole=0.4)
        fig_ativo.update_traces(rotation=90, direction='counterclockwise')
        fig_ativo.update_layout(legend=dict(traceorder='normal', itemsizing='constant'))
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    # Configuração de alinhamento textual explícito
    config_colunas = {
        'Ativo': st.column_config.TextColumn("Ativo", alignment="center"),
        'Classe': st.column_config.TextColumn("Classe", alignment="center"),
        'Preço Atual': st.column_config.TextColumn("Preço Atual", alignment="center"),
        'Qtd': st.column_config.TextColumn("Qtd", alignment="center"),
        'Total Atual': st.column_config.TextColumn("Total Atual", alignment="center"),
        'Part. %': st.column_config.TextColumn("Part. %", alignment="center")
    }
        
    # Exibição estritamente travada para leitura e totalmente centralizada
    st.dataframe(
        df_exibicao, 
        use_container_width=True, 
        hide_index=True, 
        column_config=config_colunas
    )

with aba_novos_aportes:
    st.subheader('💡 Área para planejamento futuro')
    st.info('Aqui nós vamos programar os botões para salvar as compras mês a mês no banco de dados!')
