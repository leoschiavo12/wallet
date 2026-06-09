import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ... (seu código anterior de processamento de dados permanece igual)

with aba_dash:
    c1, c2 = st.columns([1, 1.5]) # Ajuste de proporção para o gráfico ficar mais discreto
    c1.metric("Patrimônio Total", f"R$ {total_geral:,.2f}")
    
    # Rosca de Classes - Tamanho reduzido e centralizado
    fig_donut = px.pie(df_resumo_classe, values='Total Atual', names='Classe', hole=0.75, 
                       color_discrete_sequence=px.colors.sequential.Blues_r)
    fig_donut.update_traces(textinfo='percent+label', textposition='outside', sort=False)
    fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=200, showlegend=False)
    c2.plotly_chart(fig_donut, use_container_width=True)
    
    st.markdown('---')
    
    # Gráfico de Barras com Escalas Invertidas
    df_ativo = df.sort_values(by='Total Atual', ascending=False)
    
    # Criamos o subplots, mas invertemos o uso do secondary_y
    fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Eixo Primário (Direita) - Total (R$)
    fig_ativo.add_trace(go.Bar(x=df_ativo['Ativo'], y=df_ativo['Total Atual'], marker_color='#1E88E5'), secondary_y=False)
    
    # Eixo Secundário (Esquerda) - Part (%)
    fig_ativo.add_trace(go.Scatter(x=df_ativo['Ativo'], y=df_ativo['Part. %'], mode='markers', marker=dict(color='rgba(0,0,0,0)')), secondary_y=True)
    
    fig_ativo.update_layout(height=350, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', showlegend=False)
    
    # Invertendo os títulos e posicionamentos
    fig_ativo.update_yaxes(title_text="Total (R$)", secondary_y=False, showgrid=True, gridcolor='#333', side='right')
    fig_ativo.update_yaxes(title_text="Participação (%)", secondary_y=True, showgrid=False, side='left')
    
    st.plotly_chart(fig_ativo, use_container_width=True)
