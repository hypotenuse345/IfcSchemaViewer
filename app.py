import streamlit as st

from ifc_schema_viewer.apps.viewer import IfcSchemaViewerApp

st.set_page_config(page_title="IFC4.3 Viewer", page_icon="📊", layout="wide")

app = IfcSchemaViewerApp()
app.run()