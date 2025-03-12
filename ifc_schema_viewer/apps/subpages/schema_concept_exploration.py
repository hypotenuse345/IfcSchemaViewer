import streamlit as st
from streamlit_echarts import st_echarts
from streamlit_extras.grid import grid as st_grid

import rdflib
from rdflib import RDF, RDFS, OWL, SKOS, Dataset

from typing import Optional, List, Dict, Any, Literal, Union

import pandas as pd

from .base import SubPage

from ...utils import EchartsUtility, GraphAlgoUtility

class SchemaExplorationSubPage(SubPage):
    def display_basic_info(self):
        st.markdown("## Schema基本信息")
    
    def render(self):
        with st.sidebar:
            sidetab1, sidetab2 = st.tabs(["📝 基本信息", "👨‍💻 开发者信息"])
        
        with sidetab1:
            self.display_basic_info()
            
        self.display_creator_widget(sidetab2)