import streamlit as st
from streamlit_echarts import st_echarts
from streamlit_extras.grid import grid as st_grid
from streamlit_extras.markdownlit import mdlit

import rdflib
from rdflib import RDF, RDFS, OWL, SKOS, Dataset

from typing import Optional, List, Dict, Any, Literal, Union

import pandas as pd

from .base import SubPage

from ...utils import EchartsUtility, GraphAlgoUtility

ONT = rdflib.Namespace("http://www.semantic.org/zeyupan/ontologies/CoALA4IFC_Schema_Ont#")
INST = rdflib.Namespace("http://www.semantic.org/zeyupan/instances/CoALA4IFC_Schema_Inst#")

class SchemaExplorationSubPage(SubPage):
    _predicate_map : Dict[str, str] = {
            RDF.type: "类型",
            RDFS.label: "标签",
            RDFS.comment: "注释",
            RDFS.isDefinedBy: "定义",
            RDFS.seeAlso: "参见",
            RDFS.subClassOf: "继承自父类",
            RDFS.subPropertyOf: "继承自父属性",
            OWL.equivalentClass: "等价类",
            ONT["name"]: "名称",
            ONT["major"]: "主版本序号",
            ONT["minor"]: "次版本序号",
            ONT["addendums"]: "补丁版本序号",
            ONT["corrigendum"]: "修正版本序号",
        }    
    def display_basic_info(self):
        predicate_map = self._predicate_map
        
        def show_more(obj, g: rdflib.Graph):
            if isinstance(obj, rdflib.Literal):
                return obj
            elif isinstance(obj, rdflib.URIRef):
                o_label = obj.n3(g.namespace_manager)
                return f"[{o_label}]({obj})"
            # metadata = "[\n\n"
            metadata = ""
            for p, o in g.predicate_objects(subject=obj):
                p_label = p.n3(g.namespace_manager)
                if p_label == "rdf:first" or p_label == "rdf:rest":
                    if o == RDF.nil:
                        continue
                    metadata += f"\n\n{show_more(o, g)}\n\n\n\n"
                else:
                    if p in predicate_map:
                        p_label = predicate_map[p]
                    metadata += f"&emsp;&emsp;**{p_label}**: {show_more(o, g)};"
            # metadata += "]\n\n"
            return metadata
        
        # @st.cache_resource
        def get_metadata_of_ifc_schema(_g: rdflib.Graph)-> str:
            metadata = ""
            for root_node in _g.subjects(RDF.type, ONT["IfcSchema"], unique=True):
                metadata += f"**根节点**: [{root_node.n3(_g.namespace_manager)}]({root_node})\n\n"
                for p, o in _g.predicate_objects(subject=root_node):
                    p_label = p.n3(_g.namespace_manager)
                    if p in predicate_map:
                        p_label = predicate_map[p]
                    metadata += f"&emsp;&emsp;**{p_label}**: {show_more(o, _g)}\n\n"
            return metadata
                
        ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
        with st.container():
            metadata = get_metadata_of_ifc_schema(ifc_schema_graph)
            if metadata:
                with st.popover("**元数据**", use_container_width=True):
                    st.markdown(metadata)
            else:
                st.write("未找到元数据")
        with st.container():
            st.image("./resources/screenshots/IFC4_layered_architecture.png")
            mdlit("@(Know more about IFC Architecture)(https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/content/introduction.htm)")

        # st.write(f"图谱中节点数量: {len(ifc_schema_graph)}")
        # st.write(f"共计{len(ifc_schema_graph)}个三元组在这个图谱中")
    
    @st.fragment
    def display_concept_groups_widget(self):
        ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
        
        for root_node in ifc_schema_graph.subjects(RDF.type, ONT["IfcSchema"], unique=True):
            results = ifc_schema_graph.query(f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT ?data_schema ?ds_name WHERE
            {{
                ?data_schema rdf:type <{ONT["Layer"]}> ;
                    skos:inScheme <{root_node}>;
                    <{ONT["name"]}> ?ds_name.
            }}
            """)
            data_schemas = {result_row["ds_name"]: result_row["data_schema"] for result_row in results}
            grid = st_grid([2,1])
            main_col, info_graph_col = grid.container(), grid.container()
            with main_col:
                selected_layer = st.selectbox("概念层", options=data_schemas.keys())
                st.write(f"**{selected_layer}** is selected")
    
    def render(self):
        with st.sidebar:
            sidetab1, sidetab2 = st.tabs(["📝 基本信息", "👨‍💻 开发者信息"])
        
        with sidetab1:
            self.display_basic_info()
            
        self.display_creator_widget(sidetab2)
        
        # 占位： 主页面
        main_col = st.container()
        with main_col:
            maintab1, maintab2, maintab3, maintab4, maintab5 = st.tabs([
                "📝 按概念组合查看",
                "📚 命名空间",
                "🌐 本体可视化",
                "🏷️ 类", 
                "🔗 属性",])
            
            with maintab1.container():
                self.display_concept_groups_widget()
