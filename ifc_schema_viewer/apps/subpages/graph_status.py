import streamlit as st
from streamlit_echarts import st_echarts
from streamlit_extras.grid import grid as st_grid

import rdflib
from rdflib import RDF, RDFS, OWL, SKOS, Dataset

from typing import Optional, List, Dict, Any, Literal, Union

import pandas as pd

from .base import SubPage

from ...utils import EchartsUtility, GraphAlgoUtility

class GraphStatusSubPage(SubPage):
    def display_basic_info(self):
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
    
    @st.fragment
    def display_subgraph_statistics(self):
        import math
        graphs = self.ifc_schema_dataset.graphs()
        graphs = {str(graph.identifier.n3(self.ifc_schema_dataset.namespace_manager)): graph for graph in graphs}
        
        grid = st_grid([1,1])
        grid.metric("IFC4.3数据模式三元组数量", len(graphs["ifc:IFC_SCHEMA_GRAPH"]))
        grid.metric("IFC4.3数据模式本体三元组数量", len(graphs["<urn:x-rdflib:default>"]))
        num_in_column = 4
        
        search_value = st.text_input("请输入查询关键词", key="search_subgraph")
        
        subgraph_info = {}
        for i, graph_name in enumerate(graphs.keys()):
            if graph_name in ["ifc:IFC_SCHEMA_GRAPH", "<urn:x-rdflib:default>"]:
                continue
            if search_value:
                if search_value.lower() not in graph_name.lower(): continue
            if graph_name.startswith("ifc:CC_"):
                name = graph_name[7:][:-6].replace("_", " ")
            else:
                name = graph_name
            subgraph_info[name] = len(graphs[graph_name])
        
        with st.container(border=True):
            sort_option = st.radio("排序方式", ["按名称", "按大小(降序)","按大小(升序)"], horizontal=True, label_visibility="collapsed")
            if sort_option == "按名称":
                subgraph_info = {k: v for k, v in sorted(subgraph_info.items(), key=lambda item: item[0])}
            elif sort_option == "按大小(降序)":
                subgraph_info = {k: v for k, v in sorted(subgraph_info.items(), key=lambda item: item[1], reverse=True)}
            elif sort_option == "按大小(升序)":
                subgraph_info = {k: v for k, v in sorted(subgraph_info.items(), key=lambda item: item[1])}
            grid = st_grid(*[[1,]*num_in_column]*(math.ceil(1.0*len(subgraph_info)/num_in_column)))
            for i, (graph_name, size) in enumerate(subgraph_info.items()):
                grid.metric(graph_name, size)
    
    @st.fragment
    def display_namespaces(self):
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
    
    def _get_inheritance_map(self, echarts_graph_info, predicate: rdflib.URIRef, obj_range: List[str]):
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
        
    
    @st.fragment         
    def render_class_hierarchy(self, option_to_label_visualization: bool=False):
        echarts_graph_info = {}
        echarts_graph_info["nodes"] = []
        echarts_graph_info["links"] = []
        echarts_graph_info["categories"] = []
        # echarts_graph_info["categories"].append({"name": "Class"})
        
        # id_map = {}
        type_list = self.classes
        
        # id_map[RDFS.subClassOf.n3(self.ifc_schema_dataset.namespace_manager)] = RDFS.subClassOf
        self._get_inheritance_map(echarts_graph_info, RDFS.subClassOf, type_list)
        
        # echarts_graph_info["label"] = 
        s = st_echarts(
            EchartsUtility.create_normal_echart_options(echarts_graph_info, f"Class Hierarchy\n\nTotal:{len(type_list)}", label_visible=option_to_label_visualization), 
            height="500px",
            events={
                "click": "function(params) { return params.value }",
            }
        )
        return s
    
    @st.fragment
    def render_property_hierarchy(self, option_to_label_visualization: bool=False):
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
        self._get_inheritance_map(echarts_graph_info, RDFS.subPropertyOf, props_to_df["URIRef"])
        
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
    def display_metadata(self, node_iri, container):
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
    
    @st.fragment
    def ontology_visualization(self):
        grid = st_grid([5, 1])
        option_to_visualize = grid.selectbox("选择要可视化的内容", ["类继承关系", "属性继承关系"], label_visibility="collapsed")
        option_to_label_visualization = grid.checkbox("是否显示标签")
        
        grid = st_grid([2, 1])
        
        main_col, info_col = grid.container(), grid.container()
        with main_col:
            
            # if st.button("可视化", use_container_width=True):
            with st.spinner("正在生成图...", show_time=True):
                if option_to_visualize == "类继承关系":
                    selected_iri = self.render_class_hierarchy(option_to_label_visualization)   # Echarts方式
                elif option_to_visualize == "属性继承关系":
                    selected_iri = self.render_property_hierarchy(option_to_label_visualization)
                st.success("已生成图！")
        if selected_iri:
            self.display_metadata(selected_iri, info_col)
    def _get_namespace_category(self, a_label: str, category_map:Dict[str, int], echarts_graph_info: Dict[str, Any]):
        namespace = a_label.split(':')[0]
        if namespace not in category_map:
            category_map[namespace] = len(category_map)
            echarts_graph_info["categories"].append({
                "name": namespace
        })
        return category_map[namespace]
    
    def _create_node_by_categorizing_namespace(self, a_label: str, category_map:Dict[str, int], echarts_graph_info: Dict[str, Any]):
        echarts_graph_info["nodes"].append({
            "id": a_label, "name": a_label, 
            "category": self._get_namespace_category(a_label, category_map, echarts_graph_info)})

    @st.fragment
    def render_classes(self):
        def render_selected_class_echarts(ontology_graph, class_iri, height=400):
            class_iri = rdflib.URIRef(class_iri)
            class_label = class_iri.n3(ontology_graph.namespace_manager)
            echarts_graph_info = {}
            echarts_graph_info["nodes"] = []
            echarts_graph_info["links"] = []
            echarts_graph_info["categories"] = []
            # echarts_graph_info["categories"].append({"name": "Class"})
            category_map = {}
            
            self._create_node_by_categorizing_namespace(class_label, category_map, echarts_graph_info)
            # 子类
            subclasses = ontology_graph.subjects(RDFS.subClassOf, class_iri, unique=True)
            
            # 添加节点和边
            if subclasses:
                for subclass in subclasses:
                    subclass_label = subclass.n3(ontology_graph.namespace_manager)
                    self._create_node_by_categorizing_namespace(subclass_label, category_map, echarts_graph_info)
            
                    echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(subclass_label, class_label, "rdfs:subClassOf"))
                    
            # 父类
            superclasses = ontology_graph.objects(class_iri, RDFS.subClassOf, unique=True)
            if superclasses:
                for superclass in superclasses:
                    superclass_label = superclass.n3(ontology_graph.namespace_manager)
                    if superclass_label.startswith("_:"):
                        continue
                    self._create_node_by_categorizing_namespace(superclass_label, category_map, echarts_graph_info)
                    echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(class_label, superclass_label, "rdfs:subClassOf"))

            st_echarts(EchartsUtility.create_normal_echart_options(echarts_graph_info, class_label), height=f"{height}px")
    
        grid = st_grid([2, 1])
        main_col, info_graph_col = grid.container(), grid.container()
        info_col = info_graph_col.container()
        graph_col = info_graph_col.container()
        with main_col:
            classes = self.classes

            classes = {rec.n3(self.ifc_schema_dataset.namespace_manager): rec for rec in classes if not rec.n3(self.ifc_schema_dataset.namespace_manager).startswith("_:")}
            search_value = st.text_input("请输入查询关键词", key="search_classes")
            if search_value:
                classes = {k: v for k, v in classes.items() if search_value.lower() in k.lower() or search_value.lower() in v.lower()}
                
            keys = list(classes.keys())
            values = list(classes.values())
            event = st.dataframe(
                {"Namespace": [kk.split(":")[0] for kk in keys], "LocalName": keys, "URIRef": values},
                use_container_width=True,
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun"
            )
        if event.selection["rows"]:
            with graph_col:
                selected_iri = values[event.selection["rows"][0]]
                render_selected_class_echarts(self.ifc_schema_dataset, selected_iri)
            self.display_metadata(selected_iri, info_col) 
    @st.fragment
    def render_properties(self):
        def render_selected_prop_echarts(ontology_graph, prop_iri, height=400):
            prop_iri = rdflib.URIRef(prop_iri)
            echarts_graph_info = {}
            
            echarts_graph_info["nodes"] = []
            echarts_graph_info["links"] = []
            echarts_graph_info["categories"] = []
            # echarts_graph_info["categories"].append({"name": "Property"})
            # echarts_graph_info["categories"].append({"name": "Class"})
            category_map = {}
            
            prop_label = prop_iri.n3(ontology_graph.namespace_manager)
            nodes_instantiated = [prop_label]
            self._create_node_by_categorizing_namespace(prop_label, category_map, echarts_graph_info)

            # 子属性
            subprops = ontology_graph.subjects(RDFS.subPropertyOf, prop_iri, unique=True)
            if subprops:
                for subprop in subprops:
                    subprop_label = subprop.n3(ontology_graph.namespace_manager)
                    if subprop_label not in nodes_instantiated:
                        self._create_node_by_categorizing_namespace(subprop_label, category_map, echarts_graph_info)
                        nodes_instantiated.append(subprop_label)
                    echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(subprop_label, prop_label, "rdfs:subPropertyOf"))
                    
            # 父属性
            superprops = ontology_graph.objects(prop_iri, RDFS.subPropertyOf, unique=True)
            if superprops:
                for superprop in superprops:
                    superprop_label = superprop.n3(ontology_graph.namespace_manager)
                    if superprop_label.startswith("_:"):
                        continue
                    if superprop_label not in nodes_instantiated:
                        self._create_node_by_categorizing_namespace(superprop_label, category_map, echarts_graph_info)
                        nodes_instantiated.append(superprop_label)
                    echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(prop_label, superprop_label, "rdfs:subPropertyOf"))
            # echarts_graph_info["label"] = 
            
            # owl:inverseOf
            inverse_of = ontology_graph.objects(prop_iri, OWL.inverseOf, unique=True)
            # inverse_of_re = ontology_graph.subjects(OWL.inverseOf, prop_iri, unique=True)
            if inverse_of:
                for inverse_prop in inverse_of:
                    inverse_prop_label = inverse_prop.n3(ontology_graph.namespace_manager)
                    if inverse_prop_label not in nodes_instantiated:
                        self._create_node_by_categorizing_namespace(inverse_prop_label, category_map, echarts_graph_info)
                        nodes_instantiated.append(inverse_prop_label)
                    echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(prop_label, inverse_prop_label, "owl:inverseOf", line_type="dashed", show_label=True, curveness=0.2))
                    echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(inverse_prop_label, prop_label, "owl:inverseOf", line_type="dashed", show_label=True, curveness=0.2))
            
            # rdfs:domain
            domains = ontology_graph.objects(prop_iri, RDFS.domain, unique=True)
            if domains:
                for domain in domains:
                    domain_label = domain.n3(ontology_graph.namespace_manager)
                    if domain_label not in nodes_instantiated:
                        self._create_node_by_categorizing_namespace(domain_label, category_map, echarts_graph_info)
                        nodes_instantiated.append(domain_label)
                    echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(prop_label, domain_label, "rdfs:domain", line_type="dashed", show_label=True))
                    
            # rdfs:range
            ranges = ontology_graph.objects(prop_iri, RDFS.range, unique=True)
            if ranges:
                for range in ranges:
                    range_label = range.n3(ontology_graph.namespace_manager)
                    if range_label not in nodes_instantiated:
                        self._create_node_by_categorizing_namespace(range_label, category_map, echarts_graph_info)
                        nodes_instantiated.append(range_label)
                    echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(prop_label, range_label, "rdfs:range", line_type="dashed", show_label=True))
            options = EchartsUtility.create_normal_echart_options(echarts_graph_info, prop_label)
            st_echarts(options, height=f"{height}px")
            # st.write(options)
        
        grid = st_grid([2, 1])
        main_col, info_graph_col = grid.container(), grid.container()
        info_col = info_graph_col.container()
        graph_col = info_graph_col.container()
        with main_col:
            properties = self.properties
            search_value = st.text_input("请输入查询关键词", key="search_props")
            props_to_df = {"Namespace":[], "LocalName":[], "PropType":[], "URIRef":[]}
            for prop_type in ["ObjectProperty", "DatatypeProperty", "AnnotationProperty"]:
                for prop in properties[prop_type]:
                    prop_label = prop.n3(self.ifc_schema_dataset.namespace_manager)
                    if search_value and (search_value.lower() not in prop.lower() and search_value.lower() not in prop_label.lower()):
                        continue
                    props_to_df["Namespace"].append(prop_label.split(":")[0])
                    props_to_df["PropType"].append(prop_type)
                    props_to_df["LocalName"].append(prop_label)
                    props_to_df["URIRef"].append(prop)
            event = st.dataframe(
                props_to_df,
                use_container_width=True,
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun"
            )
        if event.selection["rows"]:
            with graph_col:
                selected_iri = props_to_df["URIRef"][event.selection["rows"][0]]
                render_selected_prop_echarts(self.ifc_schema_dataset, selected_iri)
            self.display_metadata(selected_iri, info_col)
    
    
    def render(self):
        # 占位：边栏
        with st.sidebar:
            sidetab1, sidetab2 = st.tabs(["📝 基本信息", "👨‍💻 开发者信息"])
        
        with sidetab1:
            self.display_basic_info()
            
        self.display_creator_widget(sidetab2)
        
         # 占位： 主页面
        main_col = st.container()
        with main_col:
            maintab1, maintab2, maintab3, maintab4, maintab5 = st.tabs([
                "📝 子图统计",
                "📚 命名空间",
                "🌐 本体可视化",
                "🏷️ 类", 
                "🔗 属性",])
        
        with maintab1.container():
            self.display_subgraph_statistics()
            
        with maintab2.container():
            self.display_namespaces()
            
        with maintab3.container():
            self.ontology_visualization()
            
        with maintab4.container():
            self.render_classes()
            
        with maintab5.container():
            self.render_properties()