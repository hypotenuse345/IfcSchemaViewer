import streamlit as st
from streamlit_echarts import st_echarts
from streamlit_extras.grid import grid as st_grid
from streamlit_extras.markdownlit import mdlit

import rdflib
from rdflib import RDF, RDFS, OWL, SKOS, Dataset

from typing import Optional, List, Dict, Any, Literal, Union

import pandas as pd
import re

from .base import SubPage

from ...utils import EchartsUtility, GraphAlgoUtility, IfcConceptRenderer

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
            mdlit("@(Learn more about IFC schematic architecture)(https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/content/introduction.htm)")

        # st.write(f"图谱中节点数量: {len(ifc_schema_graph)}")
        # st.write(f"共计{len(ifc_schema_graph)}个三元组在这个图谱中")
    
    @st.fragment
    def display_concept_groups_widget(self):
        def replace_ifc_concept_to_link(match):
            url = f"https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/{match.group(0)}.htm"
            return f"[{match.group(0)}]({url})"
            
        def display_conceptual_group_info(selected_conceptual_group, conceptual_groups, container):
            name = selected_conceptual_group
            selected_conceptual_group = conceptual_groups[selected_conceptual_group]
            with container.popover(f"**{name}** 元数据", use_container_width=True):
                mdlit(f"**{name}** @(更多信息)(https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/{name.lower()}/content.html)")
                # mdlit(f"- **iri**: {selected_conceptual_group['iri']}")
                definitions = selected_conceptual_group["definitions"].replace("\n", "\n\n")
                pattern = r'Ifc\w+'
                mdlit(re.sub(pattern, replace_ifc_concept_to_link, definitions))
        
        def display_concept_info(selected_concept, concept_type, definitions, container):
            with container.popover(f"**{selected_concept}** 元数据", use_container_width=True):
                mdlit(f"**{selected_concept}** @(更多信息)(https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/{selected_concept}.htm)")
                mdlit(f"**{concept_type}**")
                definitions = definitions.replace("\n", "\n\n")
                pattern = r'Ifc\w+'
                mdlit(re.sub(pattern, replace_ifc_concept_to_link, definitions))
        
        ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
        
        for root_node in ifc_schema_graph.subjects(RDF.type, ONT["IfcSchema"], unique=True):
            data_schemas = IfcConceptRenderer.get_data_schemas(root_node, ifc_schema_graph)
            grid = st_grid([1,1])
            main_col, info_graph_col = grid.container(), grid.container()
            with main_col:
                selected_layer = st.selectbox("概念层", options=data_schemas.keys())
                conceptual_groups = IfcConceptRenderer.get_conceptual_groups(data_schemas[selected_layer], ifc_schema_graph)
                selected_conceptual_group = st.selectbox("概念组", options=conceptual_groups.keys())
                display_conceptual_group_info(selected_conceptual_group, conceptual_groups, info_graph_col)
                concepts = IfcConceptRenderer.get_concepts(conceptual_groups[selected_conceptual_group]["iri"], self.ifc_schema_dataset)
                selected_obj = st.dataframe(
                    concepts, hide_index=True, use_container_width=True, on_select="rerun",
                    selection_mode="single-row", column_order=["type", "name", "definitions"]
                )
                if selected_obj["selection"]["rows"]:
                    selected_index = selected_obj["selection"]["rows"][0]
                    selected_obj = concepts["iri"][selected_index]
                    selected_concept = selected_obj.fragment
                    mdlit(f"@(Learn more about **{selected_concept}** on buildingSMART official website)(https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/{selected_concept}.htm)")
                    display_concept_info(selected_concept, concepts["type"][selected_index], concepts["definitions"][selected_index], info_graph_col)
                    if st.checkbox("显示实例图结构", value=False):
                        IfcConceptRenderer.render_selected_instance_echarts(selected_obj, ifc_schema_graph, height=600)
                    selected_type = concepts["type"][selected_index]
                    with info_graph_col:
                        IfcConceptRenderer.display_selected_individual_info(selected_type, selected_obj, ifc_schema_graph)
                    # st.write(f"**{selected_obj}** is selected")
    
    def _get_psets(self, ifc_schema_graph: rdflib.Graph):
        results = ifc_schema_graph.query(
            f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?pset ?pset_name ?express_type
            WHERE {{
               ?pset rdf:type ?express_type ;
                    <{ONT["name"]}> ?pset_name.
               FILTER (?express_type = <{ONT["PropertySetTemplate"]}> || ?express_type = <{ONT["QuantitySetTemplate"]})> )
            }}
            """
        )
        psets = {}
        for result in results:
            psets[result.pset_name]= {
                "pset": result.pset,
                "express_type": result.express_type.n3(ifc_schema_graph.namespace_manager)
            }
        return psets
    
    def _display_property_sets_info_by_pset(self, ifc_schema_graph: rdflib.Graph):
        if st.session_state.get("psets", None) is None:
            psets = self._get_psets(ifc_schema_graph)
            st.session_state["psets"] = psets
        else:
            psets = st.session_state["psets"]
        
        keyword = st.text_input("输入查询关键词")
        if keyword:
            psets = {k: v for k, v in psets.items() if keyword.lower() in k.lower()}
        
        selections = st.multiselect("选择属性集", list(psets.keys()))
        if selections:
            if len(selections) > 1:
                grid = st_grid(*[[1,]*2,]*(len(selections) // 2 + len(selections) % 2))
                containers = [grid.container() for i in range(len(selections))]
            else:
                containers = [st.container(),]
            for name, container in zip(selections, containers):
                pset = psets[name]
                with container:
                    IfcConceptRenderer.display_selected_individual_info(
                        express_type=pset["express_type"],
                        individual_iri=pset["pset"],
                        ifc_schema_graph=ifc_schema_graph
                    )
                
    def _get_entities(self, ifc_schema_graph: rdflib.Graph):
        results = ifc_schema_graph.query(
            f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?entity ?entity_name ?express_type
            WHERE {{
               ?entity rdf:type ?express_type ;
                    <{ONT["name"]}> ?entity_name.
               FILTER (?express_type = <{ONT["Entity"]}>)
            }}
            """
        )
        entities = {}
        for result in results:
            entities[result.entity_name]= {
                "entity": result.entity,
                "express_type": result.express_type.n3(ifc_schema_graph.namespace_manager)
            }
        return entities
    
    def _display_property_sets_info_by_entity(self, ifc_schema_graph: rdflib.Graph):
        if st.session_state.get("entities", None) is None:
            entities = self._get_entities(ifc_schema_graph)
            st.session_state["entities"] = entities
        else:
            entities = st.session_state["entities"]
        
        keyword = st.text_input("输入查询关键词")
        if keyword:
            entities = {k: v for k, v in entities.items() if keyword.lower() in k.lower()}
        
        selections = st.multiselect("选择实体", list(entities.keys()))
        if selections:
            with st.spinner("正在查询中..."):
                if len(selections) > 1:
                    grid = st_grid(*[[1,]*2,]*(len(selections) // 2 + len(selections) % 2))
                    containers = [grid.container() for i in range(len(selections))]
                else:
                    containers = [st.container(),]
                for name, container in zip(selections, containers):
                    entity = entities[name]
                    with container:
                        IfcConceptRenderer.display_selected_individual_info(
                            express_type=entity["express_type"],
                            individual_iri=entity["entity"],
                            ifc_schema_graph=ifc_schema_graph
                        )
    
    @st.fragment
    def display_property_sets_info_widget(self):
        ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
        
        search_option = st.radio("选择检索方式", ["按属性集检索", "按实体检索"], horizontal=True, label_visibility="collapsed")
        
        if search_option == "按属性集检索":
            self._display_property_sets_info_by_pset(ifc_schema_graph)
        elif search_option == "按实体检索":
            self._display_property_sets_info_by_entity(ifc_schema_graph)
    
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
                "📝 按概念组查看",
                "📚 属性集检索",
                "🌐 实体继承关系",
                "🏷️ 枚举类", 
                "🔗 导出类型",])
            
            with maintab1.container():
                self.display_concept_groups_widget()
            
            with maintab2.container():
                self.display_property_sets_info_widget()
