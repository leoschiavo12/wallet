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

# --- PREPARAÇÃO DOS DADOS PARA GRÁFICOS ---
df['Carteira'] = ''

# Agrupamento por Classe em ordem decrescente de valor para fixar o maior na base
df_resumo_classe = df.groupby(['Carteira', 'Classe'])['Total Atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values(by='Total Atual', ascending=False).reset_index(drop=True)
df_resumo_classe['Texto_Label'] = df_resumo_classe['Total Atual'].apply(lambda x: f"R$ {x:,.2f}")

mapa_cores = {
    'FII': '#26a69a',           
    'Tesouro Direto': '#29b6f6', 
    'ETF': '#ff8a80',            
    'Cripto': '#ff5252'          
}

# Ordenação dos ativos (Maior para o menor patrimônio)
df_ativos_grafico = df.sort_values(by='Total Atual', ascending=False).reset_index(drop=True)
df_ativos_grafico['Texto_Label'] = df_ativos_grafico['Part. %'].apply(lambda x: f"{x:.2f}%" if x > 1.5 else "")

df_tabela = df.sort_values(by='Total Atual', ascending=False)
df_tabela = df_tabela[['Ativo', 'Classe', 'Preço Atual', 'Qtd', 'Total Atual', 'Part. %']]

# 5. Interface Gráfica
aba_dash, aba_detalhe, aba_novos_aportes = st.tabs(["dashboard", "detalhe", "Simular Novos Aportes"])

with aba_dash:
    st.metric(label="Valor Total do Patrimônio Real", value=f"R$ {total_geral:,.2f}")
    
    # Legenda Superior Dinâmica (Pílulas)
    html_legenda = "<div style='display: flex; gap: 20px; flex-wrap: wrap; margin-top: -10px; margin-bottom: 20px;'>"
    for _, row in df_resumo_classe.iterrows():
        perc = (row['Total Atual'] / total_geral * 100) if total_geral > 0 else 0
        html_legenda += f"<div style='background-color: #f0f2f6; padding: 4px 12px; border-radius: 15px; font-size: 14px; color: #31333F; font-weight: 500;'><span style='color: #666;'>{row['Classe']}:</span> {perc:.2f}%</div>"
    html_legenda += "</div>"
    st.markdown(html_legenda, unsafe_allow_html=True)
    
    st.markdown('---')
    
    col1, col2 = st.columns(2)
    with col1:
        # Gráfico por Classe (Escala Y 100% autogerida pelo Plotly baseado no volume em R$)
        fig_classe = px.bar(df_resumo_classe, x='Carteira', y='Total Atual', color='Classe', title='Distribuição por Classe', color_discrete_map=mapa_cores, text='Texto_Label')
        
        fig_classe.update_layout(
            xaxis=dict(title="", showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(title="", showgrid=True, zeroline=False, autorange=True), # Autorange garante adaptação infinita de valores
            barmode='stack',
            legend=dict(title="", traceorder="normal")
        )
        # uniformtext com min_size esconde o texto dinamicamente se o patrimônio daquela classe ficar pequeno demais no gráfico
        fig_classe.update_layout(uniformtext_minsize=10, uniformtext_mode='hide')
        fig_classe.update_traces(width=0.28, textposition='inside', textfont=dict(size=12, color="white"))
        st.plotly_chart(fig_classe, use_container_width=True)
        
    with col2:
        # Gráfico por Ativo (Escala Y percentual fixa de 0 a 100%)
        fig_ativo = px.bar(df_ativos_grafico, x='Carteira', y='Part. %', color='Ativo', title='Distribuição por Ativo', text='Texto_Label')
        
        fig_ativo.update_layout(
            xaxis=dict(title="", showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(title="", showgrid=True, zeroline=False, ticksuffix="%"),
            barmode='stack',
            legend=dict(title="", traceorder="normal")
        )
        fig_ativo.update_layout(uniformtext_minsize=9, uniformtext_mode='hide')
        fig_ativo.update_traces(width=0.28, textposition='inside', textfont=dict(size=11, color="white"))
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
    st.dataframe(df_tabela, use_container_width=True, hide_index=True, column_config=config_colunas)

with aba_novos_aportes:
    st.subheader('💡 Área para planejamento futuro')
    st.info('Aqui nós vamos programar os botões para salvar as compras mês a mês no banco de dados!')
