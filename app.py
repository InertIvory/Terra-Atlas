import json
import requests
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(
    page_title="Terra Atlas | Explore Earth",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

COUNTRIES_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_110m_admin_0_countries.geojson"
)
RIVERS_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
    "master/geojson/ne_110m_rivers_lake_centerlines.geojson"
)

st.markdown("""
<style>
    .block-container {padding-top: 1.2rem; padding-bottom: 2rem;}
    .hero {padding: 1.15rem 1.35rem; border: 1px solid rgba(128,128,128,.25);
           border-radius: 14px; margin-bottom: 1rem;}
    .hero h1 {margin: 0 0 .25rem 0; letter-spacing: -.04em;}
    .muted {opacity: .72; font-size: .92rem;}
    div[data-testid="stMetric"] {border: 1px solid rgba(128,128,128,.22);
        padding: .75rem; border-radius: 12px;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=86400, show_spinner="Loading geographic datasets…")
def load_geojson(url: str):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json()


def feature_name(feature):
    props = feature.get("properties", {})
    return (
        props.get("ADMIN") or props.get("NAME") or
        props.get("name") or props.get("NAME_EN") or "Unknown"
    )


def river_parts(geometry):
    """Yield individual coordinate sequences from GeoJSON line geometries."""
    if not geometry:
        return
    kind = geometry.get("type")
    coords = geometry.get("coordinates", [])
    if kind == "LineString":
        yield coords
    elif kind == "MultiLineString":
        yield from coords
    elif kind == "GeometryCollection":
        for item in geometry.get("geometries", []):
            yield from river_parts(item)


def build_map(countries, rivers, selected_name, show_rivers, show_labels,
              projection, map_theme):
    features = countries.get("features", [])
    locations, names, regions, populations, gdp = [], [], [], [], []
    selected_iso = None

    for feature in features:
        p = feature.get("properties", {})
        iso = p.get("ADM0_A3") or p.get("SOV_A3") or p.get("ISO_A3")
        if not iso or iso == "-99":
            continue
        name = feature_name(feature)
        locations.append(iso)
        names.append(name)
        regions.append(p.get("REGION_UN", ""))
        populations.append(p.get("POP_EST"))
        gdp.append(p.get("GDP_MD"))
        if name == selected_name:
            selected_iso = iso

    if map_theme == "Dark":
        land, ocean, border, river_color, text_color = "#17232d", "#08131e", "#718391", "#48b9d6", "#edf5f8"
    elif map_theme == "Satellite-inspired":
        land, ocean, border, river_color, text_color = "#34483d", "#101e2c", "#8b9b87", "#63c9ed", "#f4f5e9"
    else:
        land, ocean, border, river_color, text_color = "#e5e1d5", "#c7dce5", "#657782", "#2688b7", "#1b2930"

    fig = go.Figure()

    fig.add_trace(go.Choropleth(
        geojson=countries,
        locations=locations,
        z=[1] * len(locations),
        featureidkey="properties.ADM0_A3",
        customdata=list(zip(names, regions, populations, gdp)),
        colorscale=[[0, "#789b83"], [1, "#789b83"]],
        showscale=False,
        marker_line_color=border,
        marker_line_width=0.45,
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "Region: %{customdata[1]}<br>"
            "Estimated population: %{customdata[2]:,.0f}<br>"
            "GDP (US$ millions): %{customdata[3]:,.0f}"
            "<extra></extra>"
        ),
        name="Countries",
    ))

    # Emphasize the country selected in the sidebar.
    if selected_iso:
        fig.add_trace(go.Choropleth(
            geojson=countries,
            locations=[selected_iso],
            z=[1],
            featureidkey="properties.ADM0_A3",
            colorscale=[[0, "#f0b44d"], [1, "#f0b44d"]],
            showscale=False,
            marker_line_color="#fff2d4",
            marker_line_width=1.15,
            hoverinfo="skip",
            name="Selected country",
        ))

    if show_rivers:
        for feature in rivers.get("features", []):
            props = feature.get("properties", {})
            river_name = (
                props.get("name") or props.get("NAME") or
                props.get("name_en") or "Unnamed river"
            )
            lons, lats = [], []
            for part in river_parts(feature.get("geometry")):
                for point in part:
                    if len(point) >= 2:
                        lons.append(point[0])
                        lats.append(point[1])
                lons.append(None)
                lats.append(None)
            if lons:
                fig.add_trace(go.Scattergeo(
                    lon=lons, lat=lats, mode="lines",
                    line=dict(width=1.15, color=river_color),
                    text=[river_name] * len(lons),
                    hovertemplate="<b>%{text}</b><extra>River / drainage</extra>",
                    showlegend=False,
                ))

    if show_labels:
        label_lons, label_lats, label_names = [], [], []
        for feature in features:
            p = feature.get("properties", {})
            x, y = p.get("LABEL_X"), p.get("LABEL_Y")
            if x is not None and y is not None:
                label_lons.append(x)
                label_lats.append(y)
                label_names.append(feature_name(feature))
        fig.add_trace(go.Scattergeo(
            lon=label_lons, lat=label_lats, text=label_names,
            mode="text",
            textfont=dict(size=8, color=text_color),
            hoverinfo="skip", showlegend=False,
        ))

    fig.update_geos(
        projection_type=projection.lower(),
        showland=True, landcolor=land,
        showocean=True, oceancolor=ocean,
        showcountries=True, countrycolor=border,
        showcoastlines=True, coastlinecolor=border,
        showlakes=True, lakecolor=ocean,
        showrivers=False,
        showframe=False,
        bgcolor="rgba(0,0,0,0)",
        lataxis_showgrid=True, lataxis_gridcolor="rgba(130,150,160,.22)",
        lonaxis_showgrid=True, lonaxis_gridcolor="rgba(130,150,160,.22)",
    )
    fig.update_layout(
        height=660,
        margin=dict(l=0, r=0, t=5, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=text_color),
        dragmode="pan",
        uirevision="terra-atlas-map",
    )
    return fig


st.markdown("""
<div class="hero">
  <h1>🌍 Terra Atlas</h1>
  <div class="muted">An interactive field guide to our planet — countries, rivers,
  physical geography and the systems that connect them.</div>
</div>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("Map controls")
    projection = st.selectbox(
        "Globe projection",
        ["Orthographic", "Natural Earth", "Equirectangular"],
        help="Orthographic gives the globe-like view. Drag to rotate; use the scroll wheel or map controls to zoom.",
    )
    map_theme = st.selectbox("Map appearance", ["Atlas", "Dark", "Satellite-inspired"])
    show_rivers = st.toggle("Show major rivers", value=True)
    show_labels = st.toggle("Show country labels", value=False)
    st.divider()
    st.subheader("Find a country")
    st.caption("Choose a country to highlight it and inspect available facts.")

try:
    countries = load_geojson(COUNTRIES_URL)
    rivers = load_geojson(RIVERS_URL)
except Exception as exc:
    st.error("The geographic datasets could not be loaded. Check your internet connection and refresh the app.")
    st.code(str(exc))
    st.stop()

country_features = countries.get("features", [])
country_names = sorted({feature_name(f) for f in country_features})
default_index = country_names.index("South Africa") if "South Africa" in country_names else 0
with st.sidebar:
    selected_name = st.selectbox("Country", country_names, index=default_index)

selected_feature = next((f for f in country_features if feature_name(f) == selected_name), None)
selected_props = selected_feature.get("properties", {}) if selected_feature else {}

left, right = st.columns([3.25, 1], gap="large")
with left:
    st.subheader("Explore the globe")
    st.caption("Drag to rotate • Scroll to zoom • Hover over countries and rivers for information")
    figure = build_map(
        countries, rivers, selected_name, show_rivers, show_labels,
        projection, map_theme
    )
    st.plotly_chart(
        figure, use_container_width=True,
        config={
            "scrollZoom": True,
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "displaylogo": False,
            "responsive": True,
        },
    )

with right:
    st.subheader(selected_name)
    if selected_props:
        region = selected_props.get("REGION_UN") or "Not listed"
        subregion = selected_props.get("SUBREGION") or "Not listed"
        population = selected_props.get("POP_EST")
        area = selected_props.get("AREA")
        gdp = selected_props.get("GDP_MD")
        st.metric("World region", region)
        st.write(f"**Subregion:** {subregion}")
        if isinstance(population, (int, float)):
            st.metric("Estimated population", f"{population:,.0f}")
        if isinstance(area, (int, float)):
            st.metric("Land area", f"{area:,.0f} km²")
        if isinstance(gdp, (int, float)):
            st.metric("GDP estimate", f"${gdp:,.0f} million")
        st.caption("Country statistics are Natural Earth estimates and may be dated or generalized.")
    st.divider()
    st.markdown("**What am I looking at?**")
    st.write(
        "Country polygons show generalized national boundaries. Blue lines represent "
        "major mapped rivers and drainage centerlines. Small rivers and local waterways "
        "are not included at this global map scale."
    )

st.divider()
st.subheader("A planet to investigate")
topic1, topic2, topic3 = st.columns(3)
with topic1:
    st.markdown("#### 🌊 Hydrology")
    st.write("Trace river systems from source regions to deltas. Explore how water links mountains, farms, cities and oceans.")
with topic2:
    st.markdown("#### 🏔️ Physical geography")
    st.write("Compare continents, coastlines, deserts, mountain systems and the major physical features of Earth.")
with topic3:
    st.markdown("#### 🧭 Human geography")
    st.write("Use the map as a foundation for studying population, migration, borders, trade and urbanization.")

with st.expander("Data, resolution and limitations"):
    st.markdown("""
    - **Country boundaries and major rivers:** Natural Earth vector datasets.
    - **Scale:** This first version uses the 1:110m global datasets. They are designed for
      world-scale viewing, not detailed local navigation.
    - **Boundaries:** Political boundaries can be disputed. Natural Earth applies its own
      cartographic representation; the map should not be treated as a legal boundary authority.
    - **Statistics:** Population and GDP fields are estimates in the source dataset, not live figures.
    - **No live tracking:** This app does not track people, animals, migration flows or current events.
    """)

st.caption("Terra Atlas • Version 0.1 • Built with Streamlit + Plotly + Natural Earth")
