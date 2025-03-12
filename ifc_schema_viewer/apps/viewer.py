import streamlit as st
from streamlit_extras.grid import grid as st_grid
from streamlit_echarts import st_echarts
from streamlit_extras.badges import badge

from pydantic import BaseModel, Field, PrivateAttr
from typing import Optional, List, Dict, Any, Literal, Union

import pandas as pd
import rdflib
from rdflib import RDF, RDFS, OWL, SKOS, Dataset
import os

ONT = rdflib.Namespace("http://www.semantic.org/zeyupan/ontologies/CoALA4IFC_Schema_Ont#")
INST = rdflib.Namespace("http://www.semantic.org/zeyupan/instances/CoALA4IFC_Schema_Inst#")

from ..utils import EchartsUtility, GraphAlgoUtility

from .base import StreamlitBaseApp
from .subpages import GraphStatusSubPage, SubPage, SchemaExplorationSubPage

class IfcSchemaViewerApp(StreamlitBaseApp):
    
    _graph_status_subpage: GraphStatusSubPage = PrivateAttr()
    @property
    def graph_status_subpage(self) -> GraphStatusSubPage:
        return self._graph_status_subpage
    
    _schema_exploration_subpage: SchemaExplorationSubPage = PrivateAttr()
    @property
    def schema_exploration_subpage(self) -> SchemaExplorationSubPage:
        return self._schema_exploration_subpage
    
    
    def parse_ifc_schema_dataset(self):
        def get_properties(g: rdflib.Dataset):
            property_dict = {}
            property_dict["ObjectProperty"] = [rec["property"] for rec in g.query("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?property WHERE {
                ?property rdf:type owl:ObjectProperty .
            }""")]
            property_dict["DatatypeProperty"] = [rec["property"] for rec in g.query("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?property WHERE {
                ?property rdf:type owl:DatatypeProperty .
            }""")]
            property_dict["AnnotationProperty"] = [rec["property"] for rec in g.query("""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?property WHERE {
                ?property rdf:type owl:AnnotationProperty .
            }""")]
            return property_dict
        
        if not os.path.isfile("./resources/knowledge_graphs/ifc_schema.trig") or not os.path.isfile("./resources/ontologies/skos.rdf"):
            st.error("IFC Schema Graph not found. Please check the resources.")
            st.stop()
        with st.spinner("Parsing IFC Schema Graph to RDFLib Dataset...", show_time=True):
            dataset = Dataset()
            dataset.parse("./resources/knowledge_graphs/ifc_schema.trig", format="trig")
            dataset.parse("./resources/ontologies/skos.rdf", format="xml")
        st.session_state.ifc_schema_dataset = dataset
        classes = set(dataset.subjects(predicate=RDF.type, object=OWL.Class, unique=True))
        for so in dataset.subject_objects(predicate=RDFS.subClassOf, unique=True):
            classes.add(so[0])
            classes.add(so[1])
        classes = [clss for clss in classes if not clss.n3(dataset.namespace_manager).startswith("_:")]
        st.session_state.classes = classes
        properties = get_properties(dataset)
        st.session_state.properties = properties
        
        st.rerun()
    
    def run(self):
        if st.session_state.get("ifc_schema_dataset", None) is None:
            self.parse_ifc_schema_dataset()
        
        # 建立引用
        self._graph_status_subpage = GraphStatusSubPage()
        self._schema_exploration_subpage = SchemaExplorationSubPage()
        
        # 使用streamlit的侧边栏组件，创建一个下拉选择框，用于选择子页面
        with st.sidebar:
            st.header("🔍 IFC4.3 Schema Viewer", divider=True)
            st.info("For educational purposes only.")
            # 下拉选择框的标签为“子页面导航”，选项为“图谱构成”
            subpage_option = st.selectbox("子页面导航", ["图谱总体构成", "数据模式概念探索"])
        
        # 判断用户选择的子页面是否为“图谱构成”
        if subpage_option == "图谱总体构成":
            self.graph_status_subpage.render()
        elif subpage_option == "数据模式概念探索":
            self.schema_exploration_subpage.render()

        # with st.sidebar: 
        #     st.divider()
        #     badge(type="github", name="hypotenuse345/IfcSchemaViewer")