import streamlit as st
from streamlit_echarts import st_echarts
from streamlit_extras.grid import grid as st_grid
from streamlit_extras.markdownlit import mdlit

import rdflib
from rdflib import RDF, RDFS, OWL, SKOS, Dataset

from typing import Optional, List, Dict, Any, Literal, Union

import pandas as pd
import re

from ifc_schema_viewer.utils.timer import timer_wrapper
from .rdf_query import RDFQuerySubPage

from .ifc_schema import IfcConceptRenderer, PSetCollectionInfo, EnumerationCollectionInfo, EntityCollectionInfo, DerivedTypeCollectionInfo

ONT = rdflib.Namespace("http://www.semantic.org/zeyupan/ontologies/CoALA4IFC_Schema_Ont#")
INST = rdflib.Namespace("http://www.semantic.org/zeyupan/instances/CoALA4IFC_Schema_Inst#")

class SchemaExplorationSubPage(RDFQuerySubPage):
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
    @timer_wrapper
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
    @timer_wrapper
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
        
        if st.checkbox("显示概念组信息", value=False):
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
    
    @timer_wrapper
    def _display_property_sets_info_by_pset(self, ifc_schema_graph: rdflib.Graph):
        if st.session_state.get("psets", None) is None:
            psets = PSetCollectionInfo(rdf_graph=ifc_schema_graph)
            st.session_state["psets"] = psets
        else:
            psets = st.session_state["psets"]
        
        psets.render()
            
    def _get_psets_by_entity(self, ifc_schema_graph: rdflib.Graph, entity: str):
        query_str = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT DISTINCT ?pset ?pset_name ?express_type
            WHERE {{
               ?pset rdf:type ?express_type ;
                    <{ONT["name"]}> ?pset_name;
                    <{ONT["applicableTo"]}> ?ae.
               ?ae <{ONT["subClassOf"]}>* <{entity}>.
               
                FILTER (?express_type = <{ONT["PropertySetTemplate"]}> || ?express_type = <{ONT["QuantitySetTemplate"]}> )
            }}
            """
        # st.code(query_str)
        results = ifc_schema_graph.query(
            query_str
        )
        psets = {}
        for result in results:
            psets[result.pset_name] = {
                "pset": result.pset,
                "name": result.pset_name,
                "express_type": result.express_type.n3(ifc_schema_graph.namespace_manager)
            }
        return psets
    
    @timer_wrapper
    def _display_property_sets_info_by_entity(self, ifc_schema_graph: rdflib.Graph):
        if st.session_state.get("entities", None) is None:
            entities = EntityCollectionInfo(rdf_graph=ifc_schema_graph)
            st.session_state["entities"] = entities
        else:
            entities = st.session_state["entities"]
        
        entities, selections = entities.render_multiselect()
        psets = {}
        for name in selections:
            entity = entities[name]
            for pset_name, pset in self._get_psets_by_entity(ifc_schema_graph, entity["entity"]).items():
                psets[pset_name] = pset
        
        selections = st.multiselect("选择属性集", list(psets.keys()), key="按实体选择属性集")
        
        if selections:
            with st.spinner("正在查询中..."):
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
    
    @st.fragment
    @timer_wrapper
    def display_property_sets_info_widget(self):
        if st.checkbox("显示属性集检索页面", value=False):
            ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
        
            search_option = st.radio("选择检索方式", ["按属性集检索", "按实体检索"], horizontal=True, label_visibility="collapsed")
            
            if search_option == "按属性集检索":
                self._display_property_sets_info_by_pset(ifc_schema_graph)
            elif search_option == "按实体检索":
                self._display_property_sets_info_by_entity(ifc_schema_graph)
    
    @st.fragment
    @timer_wrapper
    def display_entities_info_widget(self):
        if st.checkbox("显示实体检索页面", value=False):
            ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
        
            if st.session_state.get("entities", None) is None:
                entities = EntityCollectionInfo(rdf_graph=ifc_schema_graph)
                st.session_state["entities"] = entities
            else:
                entities = st.session_state["entities"]
                
            entities.render()
    
    @st.fragment
    @timer_wrapper
    def display_enumerations_widget(self):
        if st.checkbox("显示枚举检索页面", value=False):
            ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
        
            if st.session_state.get("enumerations", None) is None:
                enumerations = EnumerationCollectionInfo(rdf_graph=ifc_schema_graph)
                st.session_state["enumerations"] = enumerations
            else:
                enumerations = st.session_state["enumerations"]
                
            enumerations.render()
              
    @st.fragment
    @timer_wrapper
    def display_derived_types_widget(self):
        if st.checkbox("显示派生类型检索页面", value=False):
            ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
            
            if st.session_state.get("derived_types", None) is None:
                derived_types = DerivedTypeCollectionInfo(rdf_graph=ifc_schema_graph)
                st.session_state["derived_types"] = derived_types
            else:
                derived_types = st.session_state["derived_types"]
                
            derived_types.render()

    def get_express_types(self) -> List[str]:
        results = self.ifc_schema_dataset.query(f"""SELECT ?express_type WHERE {{
            ?express_type a owl:Class;
                rdfs:subClassOf+ express:SchematicConcept.
            FILTER (STRSTARTS(STR(?express_type), "http://www.semantic.org/zeyupan/ontologies/CoALA4IFC_Schema_Ont#"))
        }}""")
        return [result.express_type.fragment for result in results]

    def _generate_sparql_query_by_template(self, prefixes):
        express_types = self.get_express_types()
        grid = st_grid([1, 1])
        
        option = grid.selectbox("选择一个要检索的类型", express_types)
        limit = grid.number_input("限制返回结果数量", value=10, min_value=0)
        limit_condition = f"LIMIT {limit}" if limit > 0 else ""
        st.session_state["sparql_query"] = prefixes + f"""
SELECT DISTINCT ?s WHERE {{
    ?s a express:{option}.
}} {limit_condition}
        """
    
    def _generate_sparql_query_by_natural_language(self, prefixes):
        pass

    def generate_sparql_query_widget(self):
        """用某种方式生成SPARQL查询"""
        prefixes = """PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
PREFIX express: <http://www.semantic.org/zeyupan/ontologies/CoALA4IFC_Schema_Ont#>
PREFIX ifc: <http://www.semantic.org/zeyupan/instances/CoALA4IFC_Schema_Inst#>
            """
        
        generating_option = st.radio("选择生成方式", ["模板生成", "自然语言生成"], horizontal=True, label_visibility="collapsed")
        if generating_option == "模板生成":
            self._generate_sparql_query_by_template(prefixes)
        elif generating_option == "自然语言生成":
            self._generate_sparql_query_by_natural_language(prefixes)

    @st.fragment
    @timer_wrapper
    def display_sparql_query_widget(self):
        if st.checkbox("显示SPARQL查询页面 (开发中)", value=False):
            ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
            
            grid_layout = st_grid([1, 1])
            query_container, history_container = [grid_layout.container() for _ in range(2)]
            with query_container.container():
                generating_query_placeholder = st.empty()
                with generating_query_placeholder.container(border=True):
                    self.generate_sparql_query_widget()
                    
                with st.form("SPARQL_Query"):
                    query_str = st.text_area(
                            "Enter a SPARQL query", value="SELECT * WHERE { ?s ?p ?o } LIMIT 10" if st.session_state.get("sparql_query") is None else st.session_state["sparql_query"], 
                            key="sparql_query_editor", help="SELECT * WHERE { ?s ?p ?o }", height=200)
                    to_query = st.form_submit_button("Run Query")
                    st.session_state["sparql_query"] = query_str
                
                history_management_container = st.empty()
                if to_query:
                    self.run_sparql_query_widget(ifc_schema_graph, query_str)
            
            self.sparql_query_history_editor_widget(history_management_container,"")
            self.sparql_query_history_container_widget(history_container.container())
    
    def render(self):
        with st.sidebar:
            sidetab1, sidetab3 = st.tabs(["📝 基本信息", "👨‍💻 开发者信息"])
        
        with sidetab1:
            self.display_basic_info()
            
        self.display_creator_widget(sidetab3)
        
        # 占位： 主页面
        main_col = st.container()
        with main_col:
            maintab1, maintab2, maintab3, maintab4, maintab5, maintab6 = st.tabs([
                "📝 按概念组查看",
                "📚 属性集检索",
                "🌐 实体继承关系",
                "🏷️ 枚举类", 
                "🔗 派生类型",
                "📡 SPARQL 查询",])
            
            with maintab1.container():
                self.display_concept_groups_widget()
            
            with maintab2.container():
                self.display_property_sets_info_widget()
                
            with maintab3.container():
                self.display_entities_info_widget()

            with maintab4.container():
                self.display_enumerations_widget()

            with maintab5.container():
                self.display_derived_types_widget()

            with maintab6.container():
                self.display_sparql_query_widget()
                
            