import streamlit as st
from streamlit_extras.grid import grid as st_grid
from streamlit_echarts import st_echarts

from pydantic import BaseModel, Field, PrivateAttr
from typing import Optional, List, Dict, Any, Literal, Union

import pandas as pd
import rdflib
from rdflib import RDF, RDFS, OWL, SKOS, Dataset
import os

from ..utils import EchartsUtility, GraphAlgoUtility

from .base import StreamlitBaseApp

class IfcSchemaViewerApp(StreamlitBaseApp):
    def graph_status_subpage(self):
        # 占位：边栏
        with st.sidebar:
            sidetab1, sidetab2 = st.tabs(["基本信息 📝", "开发者信息 👨‍💻"])
        self.display_creator_widget(sidetab2)
    
    def run(self):
        with st.sidebar:
            subpage_option = st.selectbox("子页面导航", ["图谱状态"])
            
        if subpage_option == "图谱状态":
            self.graph_status_subpage()