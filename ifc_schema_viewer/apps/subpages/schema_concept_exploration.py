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
            mdlit("@(Learn more about IFC schematic architecture)(https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/content/introduction.htm)")

        # st.write(f"图谱中节点数量: {len(ifc_schema_graph)}")
        # st.write(f"共计{len(ifc_schema_graph)}个三元组在这个图谱中")
    
    @st.fragment
    def display_concept_groups_widget(self):
        def get_data_schemas(root_node, ifc_schema_graph: rdflib.Graph):
            results = ifc_schema_graph.query(f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT ?data_schema ?ds_name WHERE
            {{
                ?data_schema rdf:type <{ONT["Layer"]}> ;
                    skos:inScheme <{root_node}>;
                    <{ONT["name"]}> ?ds_name.
            }}""")
            return {result_row["ds_name"]: result_row["data_schema"] for result_row in results}
        
        def get_conceptual_groups(layer_node, ifc_schema_graph: rdflib.Graph):
            results = ifc_schema_graph.query(f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT ?conceptual_group ?cg_name ?cg_definitions WHERE
            {{
                ?conceptual_group rdf:type <{ONT["Group"]}> ;
                    <{ONT["name"]}> ?cg_name;
                    <{ONT["definitions"]}> ?cg_definitions.
                <{layer_node}> <{ONT["hasConceptualGroup"]}> ?conceptual_group.
            }}""")
            return {result_row["cg_name"]: 
                {"iri":result_row["conceptual_group"], "definitions":result_row["cg_definitions"]} for result_row in results}
        
        def get_concepts(conceptual_group_node, ifc_schema_graph: rdflib.Graph):
            results = ifc_schema_graph.query(f"""
            PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            PREFIX ifc: <http://www.semantic.org/zeyupan/instances/CoALA4IFC_Schema_Inst#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            SELECT ?concept ?concept_name ?concept_type ?concept_definitions WHERE
            {{
                GRAPH ifc:IFC_SCHEMA_GRAPH {{
                    ?concept rdf:type ?concept_type ;
                        <{ONT["name"]}> ?concept_name;
                        <{ONT["definitions"]}> ?concept_definitions.
                    <{conceptual_group_node}> ?pred ?concept.
                    FILTER (?concept_type != owl:Class)
                }}
                ?pred rdfs:subPropertyOf* <{ONT["hasConcept"]}>.
            }}""")
            concepts_4_df = {
                "type": [],
                "name": [],
                "iri": [],
                "definitions": []
            }
            for result_row in results:
                concepts_4_df["iri"].append(result_row["concept"])
                concepts_4_df["name"].append(result_row["concept_name"])
                concepts_4_df["type"].append(result_row["concept_type"].n3(ifc_schema_graph.namespace_manager))
                concepts_4_df["definitions"].append(result_row["concept_definitions"])
            
            return concepts_4_df
        
        def replace_ifc_concept_to_link(match):
            # import requests
            # Testing the URL
            url = f"https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/{match.group(0)}.htm"
            return f"[{match.group(0)}]({url})"
            # response = requests.get(url)
            # if response.status_code == 200:
            #     return f"[{match.group(0)}]({url})"
            # else:
            #     return f"[{match.group(0)}](https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/{match.group(0).lower()}/content.html)"
            
        def display_conceptual_group_info(selected_conceptual_group, conceptual_groups, container):
            name = selected_conceptual_group
            selected_conceptual_group = conceptual_groups[selected_conceptual_group]
            with container.popover("当前概念组元数据", use_container_width=True):
                mdlit(f"**{name}** @(更多信息)(https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/{name.lower()}/content.html)")
                # mdlit(f"- **iri**: {selected_conceptual_group['iri']}")
                definitions = selected_conceptual_group["definitions"].replace("\n", "\n\n")
                pattern = r'Ifc\w+'
                mdlit(re.sub(pattern, replace_ifc_concept_to_link, definitions))
        
        def display_concept_info(selected_concept, concept_type, definitions, container):
            
            with container.popover("当前概念元数据", use_container_width=True):
                mdlit(f"**{selected_concept}** @(更多信息)(https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/{selected_concept}.htm)")
                mdlit(f"**{concept_type}**")
                definitions = definitions.replace("\n", "\n\n")
                pattern = r'Ifc\w+'
                mdlit(re.sub(pattern, replace_ifc_concept_to_link, definitions))
        
        def render_selected_instance_echarts(ontology_graph: rdflib.Graph, instance_iri, height=400):
            instance_iri = rdflib.URIRef(instance_iri)
            echarts_graph_info = {"nodes":[], "links":[]}
            echarts_graph_info["categories"] = []
            echarts_graph_info["categories"].append({"name": "Instance"})
            echarts_graph_info["categories"].append({"name": "Class"})
            echarts_graph_info["categories"].append({"name": "Undefined"})
            
            category_map = {"Undefined": 2}
            
            instance_label = instance_iri.n3(ontology_graph.namespace_manager)
            nodes_instantiated = [instance_label]
            echarts_graph_info["nodes"].append({
                "id": instance_label, "name": instance_label, "category": 0})
            
            # 正向关系
            for pred, obj in ontology_graph.predicate_objects(instance_iri):
                if isinstance(obj, rdflib.Literal):
                    continue
                pred_label = pred.n3(ontology_graph.namespace_manager)
                obj_label = obj.n3(ontology_graph.namespace_manager)
                if obj_label not in nodes_instantiated:
                    if pred == RDF.type:
                        echarts_graph_info["nodes"].append({
                            "id": obj_label, "name": obj_label, "category": 1})
                    else:
                        try:
                            obj_type = [ii for ii in list(ontology_graph.objects(obj, RDF.type)) if ii!=OWL.NamedIndividual][0]
                            obj_type = obj_type.n3(ontology_graph.namespace_manager)
                            if obj_type not in category_map:
                                category_map[obj_type] = len(echarts_graph_info["categories"])
                                echarts_graph_info["categories"].append({"name": obj_type})
                        except:
                            obj_type = "Undefined"
                        echarts_graph_info["nodes"].append({
                            "id": obj_label, "name": obj_label, "category": category_map[obj_type]
                        })
                        
                    nodes_instantiated.append(obj_label)
                echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(instance_label, obj_label, pred_label, line_type="dashed", show_label=True))
                
            # 反向关系
            for subj, pred in ontology_graph.subject_predicates(instance_iri):
                pred_label = pred.n3(ontology_graph.namespace_manager)
                subj_label = subj.n3(ontology_graph.namespace_manager)
                if subj_label not in nodes_instantiated:
                    try:
                        subj_type = [ii for ii in list(ontology_graph.objects(subj, RDF.type)) if ii!=OWL.NamedIndividual][0]
                        subj_type = subj_type.n3(ontology_graph.namespace_manager)
                        if subj_type not in category_map:
                            category_map[subj_type] = len(echarts_graph_info["categories"])
                            echarts_graph_info["categories"].append({"name": subj_type})
                    except:
                        subj_type = "Undefined"
                    echarts_graph_info["nodes"].append({
                        "id": subj_label, "name": subj_label, "category": category_map[subj_type]
                    })
                echarts_graph_info["links"].append(EchartsUtility.create_normal_edge(subj_label, instance_label, pred_label, line_type="dashed", show_label=True))
            options = EchartsUtility.create_normal_echart_options(echarts_graph_info, instance_label.split(":")[1])
            st_echarts(options, height=f"{height}px")
        
        def display_enum_info(enum_iri, ifc_schema_graph: rdflib.Graph):
            enum_label = enum_iri.n3(ifc_schema_graph.namespace_manager)
            enum_info = {
                "iri": enum_iri,
                "name": enum_label,
                "members": []
            }
            results = ifc_schema_graph.query(
                f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?member_name ?member_description
                WHERE {{
                    <{enum_iri}> <{ONT["hasValue"]}> ?member .
                    ?member a <{ONT["EnumValue"]}>;
                        <{ONT["name"]}> ?member_name;
                        <{ONT["description"]}> ?member_description.
                }}
                """
            )
            for result_row in results:
                enum_info["members"].append({
                    "enum value": result_row.member_name,
                    "description": result_row.member_description
                })
            st.write(f"### {enum_iri.fragment}")
            st.dataframe(enum_info["members"], hide_index=True, use_container_width=True)
        
        def display_prop_enum(prop_enum_iri, ifc_schema_graph: rdflib.Graph):
            prop_enum_label = prop_enum_iri.n3(ifc_schema_graph.namespace_manager)
            prop_enum_info = {
                "iri": prop_enum_iri,
                "name": prop_enum_label,
                "members": []
            }
            results = ifc_schema_graph.query(
                f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?member_name ?member_description
                WHERE {{
                    <{prop_enum_iri}> <{ONT["hasValue"]}> ?member .
                    ?member a <{ONT["EnumValue"]}>;
                        <{ONT["name"]}> ?member_name;
                        <{ONT["description"]}> ?member_description.
                }}
                """
            )
            for result_row in results:
                prop_enum_info["members"].append({
                    "enum value": result_row.member_name,
                    "description": result_row.member_description
                })
            st.write(f"### {prop_enum_iri.fragment}")
            st.dataframe(prop_enum_info["members"], hide_index=True, use_container_width=True)
        
        def display_select_info(select_iri, ifc_schema_graph: rdflib.Graph):
            select_label = select_iri.n3(ifc_schema_graph.namespace_manager)
            select_info = {
                "iri": select_iri,
                "name": select_label,
                "members": []
            }
            results = ifc_schema_graph.query(
                f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?member_name
                WHERE {{
                    <{select_iri}> <{ONT["hasValue"]}> ?member .
                    ?member <{ONT["name"]}> ?member_name.
                }}
                """
            )
            for result_row in results:
                select_info["members"].append({
                    "select value": result_row.member_name,
                    "url": f"https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/{result_row.member_name}.htm"
                })
            st.write(f"### {select_iri.fragment}")
            st.dataframe(select_info["members"], hide_index=True, use_container_width=True)
        
        def display_entity_info(entity_iri, ifc_schema_graph: rdflib.Graph):
            entity_label = entity_iri.n3(ifc_schema_graph.namespace_manager)
            entity_info = {
                "iri": entity_iri,
                "name": entity_label,
                "direct_attributes": [],
                "inverse_attributes": []
            }
            results = ifc_schema_graph.query(
                f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?attr_name ?description ?optional ?direct_attr_num ?cardinality ?attrRange
                WHERE {{
                    <{entity_iri}> <{ONT["hasDirectAttribute"]}> ?attr .
                    ?attr <{ONT["name"]}> ?attr_name;
                        <{ONT["is_optional"]}> ?optional;
                        <{ONT["description"]}> ?description;
                        <{ONT["direct_attr_num"]}> ?direct_attr_num;
                        <{ONT["cardinality"]}> ?cardinality;
                        <{ONT["attrRange"]}> ?attrRange.
                }}"""
            )
            for result_row in results:
                entity_info["direct_attributes"].append({
                    "#": int(result_row.direct_attr_num),
                    "attribute": result_row.attr_name,
                    "optional": result_row.optional,
                    "cardinality": result_row.cardinality,
                    "attrRange": result_row.attrRange.fragment,
                    "description": result_row.description,
                })
            sorted(entity_info["direct_attributes"], key=lambda x: x["#"])
            st.write(f"### {entity_iri.fragment}")
            st.write(f"#### Direct Attributes")
            st.dataframe(entity_info["direct_attributes"], hide_index=True, use_container_width=True)
            
            results = ifc_schema_graph.query(
                f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT DISTINCT ?attr_name ?description ?optional ?direct_attr_num ?cardinality ?attrRange
                WHERE {{
                    <{entity_iri}> <{ONT["hasInverseAttribute"]}> ?attr .
                    ?attr <{ONT["name"]}> ?attr_name;
                        <{ONT["is_optional"]}> ?optional;
                        <{ONT["description"]}> ?description;
                        <{ONT["cardinality"]}> ?cardinality;
                        <{ONT["attrRange"]}> ?attrRange.
                }}"""
            )
            
            for result_row in results:
                entity_info["inverse_attributes"].append({
                    "#": "",
                    "attribute": result_row.attr_name,
                    "optional": result_row.optional,
                    "cardinality": result_row.cardinality,
                    "attrRange": result_row.attrRange.fragment,
                    "description": result_row.description,
                })
            st.write(f"#### Inverse Attributes")
            st.dataframe(entity_info["inverse_attributes"], hide_index=True, use_container_width=True)
        
        
        ifc_schema_graph = self.ifc_schema_dataset.get_graph(INST["IFC_SCHEMA_GRAPH"])
        
        for root_node in ifc_schema_graph.subjects(RDF.type, ONT["IfcSchema"], unique=True):
            data_schemas = get_data_schemas(root_node, ifc_schema_graph)
            grid = st_grid([2,1])
            main_col, info_graph_col = grid.container(), grid.container()
            with main_col:
                selected_layer = st.selectbox("概念层", options=data_schemas.keys())
                conceptual_groups = get_conceptual_groups(data_schemas[selected_layer], ifc_schema_graph)
                selected_conceptual_group = st.selectbox("概念组", options=conceptual_groups.keys())
                display_conceptual_group_info(selected_conceptual_group, conceptual_groups, info_graph_col)
                concepts = get_concepts(conceptual_groups[selected_conceptual_group]["iri"], self.ifc_schema_dataset)
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
                    with info_graph_col:
                        render_selected_instance_echarts(ifc_schema_graph, selected_obj)
                    selected_type = concepts["type"][selected_index]
                    if selected_type == "express:Enum":
                        display_enum_info(selected_obj, ifc_schema_graph)
                    elif selected_type == "express:PropertyEnumeration":
                        display_prop_enum(selected_obj, ifc_schema_graph)
                    elif selected_type == "express:Select":
                        display_select_info(selected_obj, ifc_schema_graph)
                    elif selected_type == "express:Entity":
                        display_entity_info(selected_obj, ifc_schema_graph)
                    # st.write(f"**{selected_obj}** is selected")
                    
    
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
                "📚 占位",
                "🌐 占位",
                "🏷️ 占位", 
                "🔗 占位",])
            
            with maintab1.container():
                self.display_concept_groups_widget()
