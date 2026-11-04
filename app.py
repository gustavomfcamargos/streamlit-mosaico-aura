import streamlit as st
import geopandas as gpd
import pandas as pd
import folium
from streamlit_folium import st_folium

# Configuração da página do Streamlit
st.set_page_config(
    page_title="Mosaico Aura | Operacional Imobiliário",
    page_icon="🏡",
    layout="wide"
)

st.title("🧭 Mosaico Aura - Controle Operacional e Polígonos")
st.markdown("Painel integrado ao QGIS classificado pela **Situação Cadastral** dos imóveis.")

# CARREGAMENTO DOS DADOS REAIS DO QGIS (GeoPackage local na mesma pasta)
@st.cache_data(ttl=60)
def carregar_dados_reais():
    # Caminho relativo: busca o arquivo na mesma pasta do app.py
    caminho_gpkg = "imoveis.gpkg"
    
    try:
        # Lê a camada 'imoveis' do GeoPackage
        gdf = gpd.read_file(caminho_gpkg, layer='imoveis')
        
        # Garante o sistema de referência SIRGAS 2000 / UTM 23S
        if gdf.crs != "EPSG:31983":
            gdf = gdf.set_crs("EPSG:31983", allow_override=True)
            
        # Se a coluna de área não existir ou estiver vazia, calcula geometricamente
        if 'Área_m2' not in gdf.columns or gdf['Área_m2'].isnull().all():
            gdf['Área_m2'] = gdf.geometry.area
            
        # Calcula o centroide em UTM para centralizar o mapa corretamente
        gdf_centroide_utm = gdf.copy()
        gdf_centroide_utm['geometry'] = gdf_centroide_utm.geometry.centroid
        
        # Converte para WGS84 (Latitude/Longitude) para renderizar no Folium
        gdf_web = gdf.to_crs("EPSG:4326")
        gdf_centroide_web = gdf_centroide_utm.to_crs("EPSG:4326")
        
        gdf_web['lat_centro'] = gdf_centroide_web.geometry.y
        gdf_web['lon_centro'] = gdf_centroide_web.geometry.x
        
        return gdf_web
        
    except Exception as e:
        st.warning(f"Aguardando dados no GeoPackage ou arquivo não encontrado. Erro: {e}")
        return gpd.GeoDataFrame()

gdf_imoveis = carregar_dados_reais()

if not gdf_imoveis.empty:
    # BARRA LATERAL COM OS FILTROS
    st.sidebar.header("🔍 Filtros Operacionais")
    
    # Filtro de Bairro
    bairros = ['Todos'] + list(gdf_imoveis['Bairro'].dropna().unique()) if 'Bairro' in gdf_imoveis.columns else ['Todos']
    bairro_sel = st.sidebar.selectbox("Bairro", bairros)

    # Filtro de Tipo de Imóvel
    tipos = ['Todos'] + list(gdf_imoveis['Tipo'].dropna().unique()) if 'Tipo' in gdf_imoveis.columns else ['Todos']
    tipo_sel = st.sidebar.selectbox("Tipo de Imóvel", tipos)

    # Filtro de Situação Cadastral
    situacoes = ['Todos'] + list(gdf_imoveis['Situação Cadastral'].dropna().unique()) if 'Situação Cadastral' in gdf_imoveis.columns else ['Todos']
    situacao_sel = st.sidebar.selectbox("Situação Cadastral", situacoes)

    # APLICANDO OS FILTROS NO DATAFRAME
    df_filtrado = gdf_imoveis.copy()
    
    if bairro_sel != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['Bairro'] == bairro_sel]
    if tipo_sel != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['Tipo'] == tipo_sel]
    if situacao_sel != 'Todos':
        df_filtrado = df_filtrado[df_filtrado['Situação Cadastral'] == situacao_sel]

    # MÉTRICAS RÁPIDAS NO TOPO
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Imóveis Filtrados", len(df_filtrado))
    col2.metric("Área Média", f"{df_filtrado['Área_m2'].mean():,.1f} m²" if not df_filtrado.empty else "0 m²")
    col3.metric("Bairro Selecionado", bairro_sel)
    col4.metric("Status", situacao_sel)

    st.markdown("---")

    # FUNÇÃO DE COR DINÂMICA BASEADA NA "Situação Cadastral"
    def cor_por_situacao(feature):
        situacao = feature['properties'].get('Situação Cadastral', '')
        if situacao == 'Em execução':
            return {'fillColor': '#3498db', 'color': '#2980b9', 'weight': 2, 'fillOpacity': 0.5} # Azul
        elif situacao == 'Vendido':
            return {'fillColor': '#e74c3c', 'color': '#c0392b', 'weight': 2, 'fillOpacity': 0.5} # Vermelho
        elif situacao == 'Em negociação':
            return {'fillColor': '#f39c12', 'color': '#d35400', 'weight': 2, 'fillOpacity': 0.5} # Laranja
        else:
            return {'fillColor': '#95a5a6', 'color': '#7f8c8d', 'weight': 2, 'fillOpacity': 0.5} # Cinza padrão

    # MAPA INTERATIVO COM OS POLÍGONOS
    lat_centro = df_filtrado['lat_centro'].mean() if not df_filtrado.empty else -19.9208
    lon_centro = df_filtrado['lon_centro'].mean() if not df_filtrado.empty else -43.9378

    m = folium.Map(location=[lat_centro, lon_centro], zoom_start=15)

    if not df_filtrado.empty:
        folium.GeoJson(
            df_filtrado,
            name="Polígonos dos Imóveis",
            style_function=cor_por_situacao,
            tooltip=folium.GeoJsonTooltip(
                fields=['Imóvel', 'Bairro', 'Situação Cadastral'],
                aliases=['Imóvel:', 'Bairro:', 'Situação:'],
                localize=True
            ),
            popup=folium.GeoJsonPopup(
                fields=['Imóvel', 'Endereço', 'Bairro', 'Tipo', 'Área_m2', 'Situação Cadastral', 'Responsável'],
                aliases=['Imóvel:', 'Endereço:', 'Bairro:', 'Tipo:', 'Área (m²):', 'Situação:', 'Responsável:'],
                localize=True,
                formatter="{:.1f}"
            )
        ).add_to(m)

    col_mapa, col_tabela = st.columns([3, 2])

    with col_mapa:
        st.subheader("🗺️ Delimitação e Classificação por Status")
        st_folium(m, width="100%", height=450)

    with col_tabela:
        st.subheader("📋 Ficha Operacional Rápida")
        if not df_filtrado.empty:
            colunas_exibir = [c for c in ['Imóvel', 'Tipo', 'Bairro', 'Área_m2', 'Situação Cadastral'] if c in df_filtrado.columns]
            df_tabela = df_filtrado[colunas_exibir].copy()
            if 'Área_m2' in df_tabela.columns:
                df_tabela['Área_m2'] = df_tabela['Área_m2'].round(1)
            st.dataframe(df_tabela, hide_index=True, height=430)
        else:
            st.warning("Nenhum imóvel encontrado com os filtros selecionados.")
else:
    st.info("O banco GeoPackage está vazio ou aguardando dados cadastrados no QGIS.")
