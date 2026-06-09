import streamlit as st
import yfinance as yf
import requests
import plotly.express as px
import pandas as pd

# 1. Configuração da Página
st.set_page_config(
    page_title="SmartWallet", 
    layout="wide", 
    page_icon="📊"
)

# Injeção de CSS para centralização de tabelas
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

# 2. Funções de Busca de Preços (Com proteção contra quedas/timeout)
def obter_precos_b3(tickers_lista):
    if not tickers_lista:
        return {}
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    precos = {}
    try:
        # Definido timeout de 7 segundos para evitar que o app fique rodando infinito se o Yahoo falhar
        dados = yf.download(
            tk_formatados, 
            period="5d", 
            group_by='ticker', 
            progress=False, 
            auto_adjust=True,
            timeout=7
        )
        for t in tickers_lista:
            chave = f"{t.upper()}.SA"
            try:
                if len(tk_formatados) > 1:
                    preco = dados[chave]['Close'].ffill().iloc[-1]
                else:
                    preco = dados['Close'].ffill().iloc[-1]
                precos[t.upper()] = float(preco) if str(preco) != 'nan' else 0.0
            except:
                precos[t.upper()] = 0.0
    except Exception as e:
        # Se der crash no Yahoo, define 0.0 temporariamente para o app não cair
        for t in tickers_lista:
            precos[t.upper()] = 0.0
    return precos

def obter_preco_btc():
    try:
        res = requests.get(
            "https://api.coinbase.com/v2/prices/BTC-BRL/spot", 
            timeout=4
        )
        return float(res.json()['data']['amount'])
    except:
        return 385000.00  # Valor de contingência caso a API da Coinbase caia

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
            # Se o Yahoo falhar e retornar 0, coloca um preço médio aproximado para testar visualmente
            if preco == 0.0:
                preco = 100.0 if classe == 'FII' else 250.0
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

# --- ESTRUTURAÇÃO VISUAL DOS GRÁFICOS ---
df['Carteira'] = ''

cores_classe = {
    'FII': '#3A6B68',            
    'Tesouro Direto': '#5F8D75',  
    'ETF': '#B86B5C',             
    'Cripto': '#D4A35D'           
}
paleta_ativos_suave = px.colors.diverging.Geyser

# 1. Gráfico de Classes
df_resumo_classe = df.groupby(['Carteira', 'Classe'])['Total Atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values(by='Total Atual', ascending=False).reset_index(drop=True)

labels_classe = []
for idx, r in df_resumo_classe.iterrows():
    p = (r['Total Atual'] / total_geral * 100) if total_geral > 0 else 0
    txt = f"<b>{r['Classe']}</b><br>R$ {r['Total Atual']:,.2f}<br>{p:.1f}%"
    labels_classe.append(txt)
df_resumo_classe['Texto_Label'] = labels_classe

# 2. Gráfico de Ativos
df_ativos_grafico = df.sort_values(by='Total Atual', ascending=False).reset_index(drop=True)

labels_legenda_ativos = []
labels_texto_interno = []
for idx, r in df_ativos_grafico.iterrows():
    labels_legenda_ativos.append(f"{r['Ativo']} ({r['Part. %']:.2f}%)")
    labels_texto_interno.append(f"{r['Part. %']:.1f}%" if r['Part. %'] > 2.5 else "")

df_ativos_grafico['Ativo_Legenda'] = labels_legenda_ativos
df_ativos_grafico['Texto_Label'] = labels_texto_interno

df_tabela = df.sort_values(by='Total Atual', ascending=False)
df_tabela = df_tabela[['Ativo', 'Classe', 'Preço Atual', 'Qtd', 'Total Atual', 'Part. %']]

# 5. Interface Gráfica
aba_dash, aba_detalhe, aba_novos_aportes = st.tabs([
    "dashboard", "detalhe", "Simular Novos Aportes"
])

with aba_dash:
    st.metric(
        label="Valor Total do Patrimônio Real", 
        value=f"R$ {total_geral:,.2f}"
    )
    
    # Legenda Superior Estilo Pílulas
    html_legenda = "<div style='display: flex; gap: 20px; flex-wrap: wrap; margin-top: -10px; margin-bottom: 20px;'>"
    for _, row in df_resumo_classe.iterrows():
        perc = (row['Total Atual'] / total_geral * 100) if total_geral > 0 else 0
        html_legenda += f"<div style='background-color: #f0f2f6; padding: 4px 12px; border-radius: 15px; font-size: 14px; color: #31333F; font-weight: 500;'><span style='color: #666;'>{row['Classe']}:</span> {perc:.2f}%</div>"
    html_legenda += "</div>"
    st.markdown(html_legenda, unsafe_allow_html=True)
    
    st.markdown('---')
    
    col1, col2 = st.columns(2)
    with col1:
        fig_classe = px.bar(
            df_resumo_classe, 
            x='Carteira', 
            y='Total Atual', 
            color='Classe', 
            title='Distribuição por Classe', 
            color_discrete_map=cores_classe, 
            text='Texto_Label'
        )
        fig_classe.update_layout(
            xaxis=dict(title="", showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(title="", showgrid=True, zeroline=False, autorange=True),
            barmode='stack',
            showlegend=False
        )
        fig_classe.update_layout(uniformtext_minsize=10, uniformtext_mode='hide')
        fig_classe.update_traces(width=0.28, textposition='inside', textfont=dict(size=12, color="white"))
        st.plotly_chart(fig_classe, use_container_width=True)
        
    with col2:
        fig_ativo = px.bar(
            df_ativos_grafico, 
            x='Carteira', 
            y='Part. %', 
            color='Ativo_Legenda', 
            title='Distribuição por Ativo', 
            text='Texto_Label',
            color_discrete_sequence=paleta_ativos_suave
        )
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
