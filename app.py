import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 1. Preparação dos dados ordenados
df_ativo = df.sort_values(by='Total Atual', ascending=False)

# 2. Criação do Gráfico com Eixos Secundários
fig_ativo = make_subplots(specs=[[{"secondary_y": True}]])

# Adicionando barras (Azuis variando do escuro para o claro)
fig_ativo.add_trace(
    go.Bar(x=df_ativo['Ativo'], y=df_ativo['Total Atual'], name='Total', 
           marker_color=px.colors.sequential.Blues_r[:len(df_ativo)]),
    secondary_y=False,
)

# Adicionando linha invisível para a escala de %
fig_ativo.add_trace(
    go.Scatter(x=df_ativo['Ativo'], y=df_ativo['Part. %'], mode='markers', 
               marker=dict(color='rgba(0,0,0,0)'), showlegend=False),
    secondary_y=True,
)

# 3. Ajustes visuais (Remoção de legendas e escalas)
fig_ativo.update_layout(
    showlegend=False,
    height=350, # Tamanho reduzido
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=40, r=40, t=40, b=40)
)

# Escala Y esquerda (R$)
fig_ativo.update_yaxes(title_text="Total (R$)", secondary_y=False, showgrid=True, gridcolor='#333')
# Escala Y direita (%)
fig_ativo.update_yaxes(title_text="Participação (%)", secondary_y=True, showgrid=False)

st.plotly_chart(fig_ativo, use_container_width=True)
