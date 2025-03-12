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
    @st.fragment
    def graph_status_subpage_display_namespaces(self):
        namespaces = self.ifc_schema_dataset.namespaces()
        namespaces = {k: v for k, v in namespaces}
        search_value = st.text_input("请输入查询关键词")
        if search_value:
            namespaces = {k: v for k, v in namespaces.items() if search_value.lower() in k.lower() or search_value.lower() in v.lower()}
            
        # 渲染，使用st.columns
        st.dataframe(
            pd.DataFrame({"Prefix": namespaces.keys(), "Namespace": namespaces.values()}),
            use_container_width=True,
            hide_index=True,
            column_order=["Prefix", "Namespace"],
        )
    
    def _graph_status_subpage_get_inheritance_map(self, echarts_graph_info, predicate: rdflib.URIRef, obj_range: List[str]):
        import numpy as np
        inheritance_map = {}
        degrees = {}
        pred_label = predicate.n3(self.ifc_schema_dataset.namespace_manager)
        obj_range_copy = set(obj_range.copy())
        category_map = {}
        for s, o in self.ifc_schema_dataset.subject_objects(predicate=predicate, unique=True):
            # 将RDF对象转换为缩写
            s_label = s.n3(self.ifc_schema_dataset.namespace_manager)
            o_label = o.n3(self.ifc_schema_dataset.namespace_manager)
            if o not in obj_range:
                if o_label.startswith("_:"):
                    continue
                else:
                    obj_range_copy.add(o)
            
            if o_label not in inheritance_map:
                inheritance_map[o_label] = []
            inheritance_map[o_label].append(s_label)
            if s_label not in degrees:
                degrees[s_label] = 1
            else:
                degrees[s_label] += 1
            if o_label not in degrees:
                degrees[o_label] = 1
            else:
                degrees[o_label] += 1
            # 在有向图中添加边，边的标签为谓词
            echarts_graph_info["links"].append(
                EchartsUtility.create_normal_edge(
                    s_label, o_label, 
                    label=pred_label
                )
            )
        
        refreshed_degrees = {}
        
        for label in degrees:
            GraphAlgoUtility.refresh_degree(degrees, inheritance_map, label, refreshed_degrees)    
        
        nodes_initiated = set()
        for i, clss in enumerate(obj_range_copy):
            s_label = clss.n3(self.ifc_schema_dataset.namespace_manager)
            if s_label in nodes_initiated:
                continue
            nodes_initiated.add(s_label)
            namespace = s_label.split(':')[0]
            if namespace not in category_map:
                category_map[namespace] = len(category_map)
                echarts_graph_info["categories"].append({
                    "name": namespace
                })
            echarts_graph_info["nodes"].append({
                "id": s_label,
                "name": s_label,
                "category": category_map[namespace],
                "symbol": 'circle',
                "symbolSize":10 + np.log(refreshed_degrees[s_label]) * 7 if s_label in refreshed_degrees else 10,
                # "symbolSize":[200, 20],
                "draggable": False,
                "value": clss
            })
            
    def graph_status_subpage_display_metadata(self, node_iri, container):
        node_iri = rdflib.URIRef(node_iri)
        metadata = ""
        metadata += f"**IRI:** {node_iri}\n\n"
        metadata += f"**Namespace:** {node_iri.n3(self.ifc_schema_dataset.namespace_manager).split(':')[0]}\n\n"
        
        prop_literals = [po for po in self.ifc_schema_dataset.predicate_objects(subject=node_iri, unique=True) if isinstance(po[1], rdflib.Literal)]
        for p, o in prop_literals:
            if p == RDFS.label:
                metadata += f"**Label ({o.language if o.language else 'en'}):** {o}\n\n"
            elif p == RDFS.comment:
                metadata += f"**Comment ({o.language if o.language else 'en'}):** {o}\n\n"
            elif p == SKOS.definition:
                metadata += f"**Definition ({o.language if o.language else 'en'}):** {o}\n\n"
            else:
                metadata += f"**{p.n3(self.ifc_schema_dataset.namespace_manager)}**: {o}\n\n"
        
        # 若当前节点是为属性，则进一步考虑owl约束
        if node_iri in self.properties["ObjectProperty"]:
            is_asymmetric = self.ifc_schema_dataset.query(
                f"ASK {{<{node_iri}> a owl:AsymmetricProperty.}}"
            )
            if is_asymmetric.askAnswer:
                # st.markdown(f"**Asymmetric:** True")
                metadata += f"**Asymmetric:** True\n\n"
            is_reflexive = self.ifc_schema_dataset.query(
                f"ASK {{<{node_iri}> a owl:ReflexiveProperty.}}"
            )
            if is_reflexive.askAnswer:
                # st.markdown(f"**Reflexive:** True")
                metadata += f"**Reflexive:** True\n\n"
            is_irreflexive = self.ifc_schema_dataset.query(
                f"ASK {{<{node_iri}> a owl:IrreflexiveProperty.}}"
            )
            if is_irreflexive.askAnswer:
                # st.markdown(f"**Irreflexive:** True")
                metadata += f"**Irreflexive:** True\n\n"
            is_symmetric = self.ifc_schema_dataset.query(
                f"ASK {{<{node_iri}> a owl:SymmetricProperty.}}"
            )
            if is_symmetric.askAnswer:
                # st.markdown(f"**Symmetric:** True")
                metadata += f"**Symmetric:** True\n\n"
            is_transitive = self.ifc_schema_dataset.query(
                f"ASK {{<{node_iri}> a owl:TransitiveProperty.}}"
            )
            if is_transitive.askAnswer:
                # st.markdown(f"**Transitive:** True")
                metadata += f"**Transitive:** True\n\n"
        # response_placeholder = st.empty()
        
        with container.container():
            st.write(f"**{node_iri.n3(self.ifc_schema_dataset.namespace_manager)}** \n\n")
            with st.expander("元数据"):
                st.markdown(metadata)
                
    def graph_status_subpage_render_class_hierarchy(self, option_to_label_visualization: bool=False):
        echarts_graph_info = {}
        echarts_graph_info["nodes"] = []
        echarts_graph_info["links"] = []
        echarts_graph_info["categories"] = []
        # echarts_graph_info["categories"].append({"name": "Class"})
        
        # id_map = {}
        type_list = self.classes
        
        # id_map[RDFS.subClassOf.n3(self.ifc_schema_dataset.namespace_manager)] = RDFS.subClassOf
        self._graph_status_subpage_get_inheritance_map(echarts_graph_info, RDFS.subClassOf, type_list)
        
        # echarts_graph_info["label"] = 
        s = st_echarts(
            EchartsUtility.create_normal_echart_options(echarts_graph_info, f"Class Hierarchy\n\nTotal:{len(type_list)}", label_visible=option_to_label_visualization), 
            height="500px",
            events={
                "click": "function(params) { return params.value }",
            }
        )
        return s
    
    def graph_status_subpage_render_property_hierarchy(self, option_to_label_visualization: bool=False):
        echarts_graph_info = {}
        echarts_graph_info["nodes"] = []
        echarts_graph_info["links"] = []
        echarts_graph_info["categories"] = []
        # echarts_graph_info["categories"].append({"name": "Property"})
        
        properties = self.properties
        
        props_to_df = {"Namespace":[], "PropType":[], "LocalName":[], "URIRef":[]}
        for prop_type in ["ObjectProperty", "DatatypeProperty", "AnnotationProperty"]:
            for prop in properties[prop_type]:
                prop_label = prop.n3(self.ifc_schema_dataset.namespace_manager)
                props_to_df["Namespace"].append(prop_label.split(":")[0])
                props_to_df["PropType"].append(prop_type)
                props_to_df["LocalName"].append(prop_label)
                props_to_df["URIRef"].append(prop)
        self._graph_status_subpage_get_inheritance_map(echarts_graph_info, RDFS.subPropertyOf, props_to_df["URIRef"])
        
        options = EchartsUtility.create_normal_echart_options(echarts_graph_info, f"Property Hierarchy\n\nTotal:{len(props_to_df['URIRef'])}", label_visible=option_to_label_visualization)
        # st.write(options)
        s = st_echarts(
            options=options,
            height="500px",
            events={
                "click": "function(params) { return params.value }",
            }
        )
        return s
    
    @st.fragment
    def graph_status_subpage_display_subgraph_info(self):
        # graphs = self.ifc_schema_dataset.graphs()
        # graphs = {str(graph.identifier.n3(self.ifc_schema_dataset.namespace_manager)): graph for graph in graphs}
        # st.write(graphs.keys())
        pass
        
        
    @st.fragment
    def graph_status_subpage_display_basic_info(self):
        graphs = self.ifc_schema_dataset.graphs()
        graphs = {str(graph.identifier.n3(self.ifc_schema_dataset.namespace_manager)): graph for graph in graphs}
            
        triplet_count = len(self.ifc_schema_dataset)
        with st.container(border=True):
            grid = st_grid([1,1], [1,1], [1,1])
            grid.metric(label="子图数量", value=len(graphs))
            grid.metric(label="三元组数量", value=triplet_count)
            CC_graphs = [graph_name for graph_name in graphs.keys() if graph_name.startswith("ifc:CC")]
            grid.metric(label="通用概念子图数量", value=len(CC_graphs))
            grid.metric(label="通用概念子图三元组数量", value=sum([len(graphs[graph_name]) for graph_name in CC_graphs]))
            ifc_schema_subgraph = graphs["ifc:IFC_SCHEMA_GRAPH"]
            grid.metric(label="IFC数据标准子图三元组数量", value=len(ifc_schema_subgraph))
            grid.container()
            # grid.container()
        
        # st.write(f"Total types: {len(self.classes)}")
        # st.write(f"Total properties: {[(prop_type, len(props)) for prop_type, props in self.properties.items()]}")
    
    @st.fragment
    def graph_status_subpage_visualization(self):
        grid = st_grid([5, 1])
        option_to_visualize = grid.selectbox("选择要可视化的内容", ["类继承关系", "属性继承关系"], label_visibility="collapsed")
        option_to_label_visualization = grid.checkbox("是否显示标签")
        
        grid = st_grid([2, 1])
        
        main_col, info_col = grid.container(), grid.container()
        with main_col:
            
            # if st.button("可视化", use_container_width=True):
            with st.spinner("正在生成图...", show_time=True):
                if option_to_visualize == "类继承关系":
                    selected_iri = self.graph_status_subpage_render_class_hierarchy(option_to_label_visualization)   # Echarts方式
                elif option_to_visualize == "属性继承关系":
                    selected_iri = self.graph_status_subpage_render_property_hierarchy(option_to_label_visualization)
                st.success("已生成图！")
        if selected_iri:
            self.graph_status_subpage_display_metadata(selected_iri, info_col)
    
    def graph_status_subpage(self):
        # 占位：边栏
        with st.sidebar:
            sidetab1, sidetab2 = st.tabs(["📝 基本信息", "👨‍💻 开发者信息"])
        
        with sidetab1:
            self.graph_status_subpage_display_basic_info()
            
        self.display_creator_widget(sidetab2)
        
        # 占位： 主页面
        main_col = st.container()
        with main_col:
            maintab1, maintab2, maintab3, maintab4, maintab5 = st.tabs([
                "📝 子图基本信息",
                "📚 命名空间",
                "🌐 本体可视化",
                "📈 图谱展示", 
                "📊 图谱分析"])
        
        with maintab1.container():
            self.graph_status_subpage_display_subgraph_info()
        with maintab2.container():
            self.graph_status_subpage_display_namespaces()
        
        with maintab3.container():
            self.graph_status_subpage_visualization()
    
    def data_schema_concept_exploration_subpage(self):
        with st.sidebar:
            sidetab1, sidetab2 = st.tabs(["📝 基本信息", "👨‍💻 开发者信息"])
            
        self.display_creator_widget(sidetab2)
        st.write("数据模式概念探索")
    
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
    
    _ifc_schema_dataset: Dataset = PrivateAttr()
    @property
    def ifc_schema_dataset(self):
        return self._ifc_schema_dataset
    
    _classes: List[str] = PrivateAttr(default_factory=list)

    @property
    def classes(self) -> List[str]:
        return self._classes

    _classes_with_individuals: List[str] = PrivateAttr(default_factory=list)

    @property
    def classes_with_individuals(self) -> List[str]:
        return self._classes_with_individuals

    _properties: Dict[str, List[str]] = PrivateAttr(default_factory=dict)
    @property
    def properties(self) -> Dict[str, List[str]]:
        return self._properties
    
    def run(self):
        if st.session_state.get("ifc_schema_dataset", None) is None:
            self.parse_ifc_schema_dataset()
        
        # 建立引用
        self._ifc_schema_dataset = st.session_state.ifc_schema_dataset
        self._classes = st.session_state.classes
        self._properties = st.session_state.properties
        
        # 使用streamlit的侧边栏组件，创建一个下拉选择框，用于选择子页面
        with st.sidebar:
            st.header("🔍 IFC4.3 Viewer", divider=True)
            st.write("For education purposes only.")
            # 下拉选择框的标签为“子页面导航”，选项为“图谱状态”
            subpage_option = st.selectbox("子页面导航", ["图谱状态", "数据模式概念探索"])
            
        # 判断用户选择的子页面是否为“图谱状态”
        if subpage_option == "图谱状态":
            # 如果是“图谱状态”，则调用self.graph_status_subpage()方法显示相应内容
            self.graph_status_subpage()
        elif subpage_option == "数据模式概念探索":
            self.data_schema_concept_exploration_subpage()