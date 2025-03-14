import rdflib
from rdflib import RDF, RDFS, OWL
import streamlit as st
from streamlit_echarts import st_echarts
from streamlit_extras.markdownlit import mdlit
from streamlit_extras.stoggle import stoggle

from pydantic import BaseModel, PrivateAttr, Field
from typing import List, Optional, Any, Dict, Annotated, Type

from .echarts import EchartsUtility
import random

ONT = rdflib.Namespace("http://www.semantic.org/zeyupan/ontologies/CoALA4IFC_Schema_Ont#")

class ConceptInfo(BaseModel):
    iri: Annotated[str, Field(description="The IRI of the concept")]
    _express_type: str = PrivateAttr("")
    
    @property
    def express_type(self):
        return self._express_type
    
    _definitions: Optional[str] = PrivateAttr(default=None)
    
    @property
    def definitions(self):
        if self._definitions is None:
            return ""
        else:
            return self._definitions.replace("\n", "\n\n")
    
    _seed: int = PrivateAttr(default=0)
    @property
    def seed(self):
        return self._seed
    
    rdf_graph: Any = Field(description="The RDF graph containing the concept information")
    
    def model_post_init(self, __context):
        if not isinstance(self.rdf_graph, rdflib.Graph):
            raise ValueError("rdf_graph must be an instance of rdflib.Graph")

    @property
    def namespace_manager(self):
        return self.rdf_graph.namespace_manager
    
    @property
    def label(self):
        return rdflib.URIRef(self.iri).fragment
    
    def display(self, container):
        raise NotImplementedError("Subclasses must implement the display method")

class TypeInfo(ConceptInfo):
    _express_type: str = PrivateAttr("express:Type")
    
    _is_referenced_by_entities: List[str] = PrivateAttr(default_factory=list)
    @property
    def is_referenced_by_entities(self):
        return self._is_referenced_by_entities
    
    def model_post_init(self, __context):
        super().model_post_init(__context)
        
        # 定义
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?definitions
            WHERE {{
                <{self.iri}> <{ONT["definitions"]}> ?definitions.
            }}"""
        )
        for result_row in results:
            self._definitions = result_row.definitions
        
        # 被哪些实体引用
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?entity_name ?entity ?attribute_name ?direct_attr_num ?cardinality
            WHERE {{
                ?attr <{ONT["attrRange"]}> <{self.iri}> ;
                    <{ONT["name"]}> ?attribute_name;
                    <{ONT["direct_attr_num"]}> ?direct_attr_num;
                    <{ONT["cardinality"]}> ?cardinality.
                ?direct_entity <{ONT["hasDirectAttribute"]}> ?attr;
                    <{ONT["superClassOf"]}>* ?entity.
                ?entity <{ONT["name"]}> ?entity_name.
                
            }}"""
        )
        for result_row in results:
            self.is_referenced_by_entities.append({
                "entity": result_row.entity_name,
                "attribute": result_row.attribute_name,
                "entity iri": result_row.entity,
                "direct_attr_num": result_row.direct_attr_num,
                "cardinality": result_row.cardinality
            })
    def display(self, container):
        with container:
            st.write("#### *Referencing Entities*")
            while True:
                try:
                    selected = st.dataframe(
                        self.is_referenced_by_entities, hide_index=True, use_container_width=True,
                        column_order=["entity", "direct_attr_num", "attribute", "cardinality"], selection_mode="single-row",
                        on_select="rerun",
                        key=f"{self.seed}_{self.iri}_referencing_entities"
                    )
                    break
                except Exception as e:
                    self._seed += 1
                
        if selected["selection"]["rows"]:
            selected_index = selected["selection"]["rows"][0]
            entity = self.is_referenced_by_entities[selected_index]
            IfcConceptRenderer.display_selected_individual_info("express:Entity", entity["entity iri"], self.rdf_graph)


class EnumInfo(TypeInfo):
    _members: List[Dict[str, str]] = PrivateAttr(default_factory=list)
    @property
    def members(self):
        return self._members
    
    _express_type: str = PrivateAttr("express:Enum")
    
    def model_post_init(self, __context):
        super().model_post_init(__context)
        
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?member_name ?member_description
            WHERE {{
                <{self.iri}> <{ONT["hasValue"]}> ?member .
                ?member a <{ONT["EnumValue"]}>;
                    <{ONT["name"]}> ?member_name;
                    <{ONT["description"]}> ?member_description.
            }}
            """
        )
        for result_row in results:
            self.members.append({
                "enum value": result_row.member_name,
                "description": result_row.member_description
            })
    
    def display(self, container):
        with container:
            stoggle("Definitions", self.definitions)
            st.write("#### *Enum Values*")
            st.dataframe(self.members, hide_index=True, use_container_width=True)
        super().display(container)
            
class PropertyEnumInfo(ConceptInfo):
    _members: List[Dict[str, str]] = PrivateAttr(default_factory=list)
    @property
    def members(self):
        return self._members
    
    _express_type: str = PrivateAttr("express:PropertyEnumeration")
    
    _applicable_pset_templates: List[Dict[str, str]] = PrivateAttr(default_factory=list)
    @property
    def applicable_pset_templates(self):
        return self._applicable_pset_templates

    def model_post_init(self, __context):
        super().model_post_init(__context)

        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?definitions
            WHERE {{
                <{self.iri}> <{ONT["definitions"]}> ?definitions.
            }}"""
        )
        for result_row in results:
            self._definitions = result_row.definitions

        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?member_name ?member_description
            WHERE {{
                <{self.iri}> <{ONT["hasValue"]}> ?member .
                ?member a <{ONT["EnumValue"]}>;
                    <{ONT["name"]}> ?member_name;
                    <{ONT["description"]}> ?member_description.
            }}
            """
        )
        for result_row in results:
            self.members.append({
                "enum value": result_row.member_name,
                "description": result_row.member_description
            })

        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?pset_template ?pset_template_name ?prop ?prop_name
            WHERE {{
                ?prop <{ONT["dataType"]}> <{self.iri}>;
                    <{ONT['name']}> ?prop_name.
                ?pset_template <{ONT["hasPropTemplate"]}> ?prop ;
                    <{ONT["name"]}> ?pset_template_name.
            }}
            """
        )
        for result_row in results:
            self.applicable_pset_templates.append({
                "pset template iri": result_row.pset_template,
                "Property Set": result_row.pset_template_name,
                "property iri": result_row.prop,
                "Property": result_row.prop_name
            })
    def display(self, container):
        with container:
            stoggle("Definitions", self.definitions)
            st.write("#### *Enum Values*")
            st.dataframe(self.members, hide_index=True, use_container_width=True)
            
        with container:
            st.write("#### *Referencing Property Set Templates*")
            while True:
                try:
                    selected = st.dataframe(
                        self.applicable_pset_templates,
                        hide_index=True,
                        use_container_width=True,
                        selection_mode="single-row",
                        on_select="rerun", column_order=["Property Set", "Property"],
                        key=f"{self.seed}_{self.iri}_referencing_pset_template"
                    )
                    break
                except:
                    self._seed += 1
        if selected["selection"]["rows"]:
            selected_index = selected["selection"]["rows"][0]
            pset = self.applicable_pset_templates[selected_index]
            IfcConceptRenderer.display_selected_individual_info("express:PropertySetTemplate", pset["pset template iri"], self.rdf_graph)


class SelectInfo(TypeInfo):
    _members: List[Dict[str, str]] = PrivateAttr(default_factory=list)
    @property
    def members(self):
        return self._members

    _express_type: str = PrivateAttr("express:Select")

    def model_post_init(self, __context):
        super().model_post_init(__context)

        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?member ?member_name ?express_type
            WHERE {{
                <{self.iri}> <{ONT["hasValue"]}> ?member .
                ?member <{ONT["name"]}> ?member_name;
                    a ?express_type.
                FILTER (STRSTARTS(str(?express_type), "{ONT}"))
            }}
            """
        )
        for result_row in results:
            self.members.append({
                "select value": result_row.member_name,
                "express type": result_row.express_type.n3(self.namespace_manager),
                "iri": result_row.member
            })
    def display(self, container):
        with container:
            stoggle("Definitions", self.definitions)
            st.write(f"#### *Select Values*")
            while True:
                try:
                    selected = st.dataframe(
                        self.members, hide_index=True, 
                        use_container_width=True, selection_mode="single-row",
                        on_select="rerun", column_order=["select value", "express type"],
                        key=f"{self.seed}_{self.iri}_select_members")
                    break
                except:
                    self._seed += 1
        if selected["selection"]["rows"]:
            selected_index = selected["selection"]["rows"][0]
            member = self.members[selected_index]
            IfcConceptRenderer.display_selected_individual_info(member["express type"], member["iri"], self.rdf_graph)
        super().display(container)

class EntityInfo(ConceptInfo):
    _express_type: str = PrivateAttr("express:Entity")
    _super_entities : List[Dict[str, str]] = PrivateAttr(default_factory=list)
    _sub_entities : List[Dict[str, str]] = PrivateAttr(default_factory=list)
    _direct_attributes : List[Dict[str, str]] = PrivateAttr(default_factory=list)
    _inverse_attributes : List[Dict[str, str]] = PrivateAttr(default_factory=list)
    _pset_templates: List[Dict[str, str]] = PrivateAttr(default_factory=list)
    
    @property
    def super_entities(self):
        return self._super_entities
    @property
    def sub_entities(self):
        return self._sub_entities
    @property
    def direct_attributes(self):
        return self._direct_attributes
    @property
    def inverse_attributes(self):
        return self._inverse_attributes
    @property
    def pset_templates(self):
        return self._pset_templates

    def model_post_init(self, __context):
        super().model_post_init(__context)

        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?definitions
            WHERE {{
                <{self.iri}> <{ONT["definitions"]}> ?definitions.
            }}"""
        )
        for result_row in results:
            self._definitions = result_row.definitions

        # 父实体
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?super_entity ?super_entity_name ?definitions
            WHERE {{
                <{self.iri}> <{ONT["subClassOf"]}>+ ?super_entity .
                ?super_entity <{ONT["name"]}> ?super_entity_name;
                    <{ONT["definitions"]}> ?definitions.
            }}"""
        )
        for result_row in results:
            self.super_entities.append({
                "type": "express:Entity",
                "name": result_row.super_entity_name,
                "iri": result_row.super_entity,
                "definitions": result_row.definitions
            })
            
        # 子实体
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?sub_entity ?sub_entity_name ?definitions
            WHERE {{
                ?sub_entity <{ONT["subClassOf"]}>+ <{self.iri}> .
                ?sub_entity <{ONT["name"]}> ?sub_entity_name;
                    <{ONT["definitions"]}> ?definitions.
            }}"""
        )
        for result_row in results:
            self.sub_entities.append({
                "type": "express:Entity",
                "name": result_row.sub_entity_name,
                "iri": result_row.sub_entity,
                "definitions": result_row.definitions
            })
        # 直接属性
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?attr_name ?description ?optional ?direct_attr_num ?cardinality ?attrRange ?express_type
            WHERE {{
                <{self.iri}> <{ONT["hasDirectAttribute"]}> ?attr .
                ?attr <{ONT["name"]}> ?attr_name;
                    <{ONT["is_optional"]}> ?optional;
                    <{ONT["description"]}> ?description;
                    <{ONT["direct_attr_num"]}> ?direct_attr_num;
                    <{ONT["cardinality"]}> ?cardinality;
                    <{ONT["attrRange"]}> ?attrRange.
                ?attrRange a ?express_type.
                FILTER (STRSTARTS(str(?express_type), "{ONT}"))
            }}"""
        )
        for result_row in results:
            self.direct_attributes.append({
                "#": int(result_row.direct_attr_num),
                "name": result_row.attr_name,
                "optional": "T" if result_row.optional else "F",
                "cardinality": result_row.cardinality,
                "range": result_row.attrRange.fragment,
                "express type": result_row.express_type.n3(self.rdf_graph.namespace_manager),
                "attr datatype": result_row.attrRange,
                "description": result_row.description,
            })
        self.direct_attributes.sort(key=lambda x: x["#"])
        
        # 间接属性
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?attr_name ?description ?optional ?direct_attr_num ?cardinality ?attrRange ?express_type
            WHERE {{
                <{self.iri}> <{ONT["hasInverseAttribute"]}> ?attr .
                ?attr <{ONT["name"]}> ?attr_name;
                    <{ONT["is_optional"]}> ?optional;
                    <{ONT["description"]}> ?description;
                    <{ONT["cardinality"]}> ?cardinality;
                    <{ONT["attrRange"]}> ?attrRange.
                ?attrRange a ?express_type.
                FILTER (STRSTARTS(str(?express_type), "{ONT}"))
            }}"""
        )
        
        for result_row in results:
            self.inverse_attributes.append({
                "#": "",
                "name": result_row.attr_name,
                "optional": "T" if result_row.optional else "F",
                "cardinality": result_row.cardinality,
                "range": result_row.attrRange.fragment,
                "express type": result_row.express_type.n3(self.namespace_manager),
                "attr datatype": result_row.attrRange,
                "description": result_row.description,
            })
            
        # 关联的属性集模板
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?pset ?pset_name ?definitions ?express_type
            WHERE {{
                <{self.iri}> <{ONT['subClassOf']}>* ?ae.
                ?pset a ?express_type;
                    <{ONT["applicableTo"]}> ?ae;
                    <{ONT["name"]}> ?pset_name;
                    <{ONT["definitions"]}> ?definitions.
                FILTER (STRSTARTS(str(?express_type), "{ONT}"))
            }}"""
        )
        for result_row in results:
            self.pset_templates.append({
                "name": result_row.pset_name,
                "iri": result_row.pset,
                "definitions": result_row.definitions,
                "express type": result_row.express_type.n3(self.namespace_manager)
            })
    
    def _display_super_entities(self, container):
        with container:
            stoggle("Definitions", self.definitions)
            st.write(f"#### *Super Entities*")
            selected_index = None
            if self.super_entities:
                while True:
                    try:
                        selected = st.dataframe(
                            self.super_entities, hide_index=True, 
                            use_container_width=True, selection_mode="single-row",
                            on_select="rerun", column_order=["type", "name", "definitions"],
                            key=f"{self.seed}_{self.iri}_super_entities")
                        break
                    except:
                        self._seed += 1
                        
                if selected["selection"]["rows"]:
                    selected_index = selected["selection"]["rows"][0]
            else:
                st.write("None")
        if selected_index is not None:
            super_entity = self.super_entities[selected_index]
            IfcConceptRenderer.display_selected_individual_info("express:Entity", super_entity["iri"], self.rdf_graph)
    
    def _display_sub_entities(self, container):
        with container:
            st.write(f"#### *Sub Entities*")
            selected_index = None
            if self.sub_entities:
                while True:
                    try:
                        selected = st.dataframe(
                            self.sub_entities, hide_index=True, 
                            use_container_width=True, selection_mode="single-row",
                            on_select="rerun", column_order=["type", "name", "definitions"],
                            key=f"{self.seed}_{self.iri}_sub_entities")
                        break
                    except:
                        self._seed += 1
                    
                if selected["selection"]["rows"]:
                    selected_index = selected["selection"]["rows"][0]
            else:
                st.write("None")
        if selected_index is not None:
            sub_entity = self.sub_entities[selected_index]
            IfcConceptRenderer.display_selected_individual_info("express:Entity", sub_entity["iri"], self.rdf_graph)
    
    def _display_direct_attributes(self, container):
        with container:
            st.write(f"#### *Direct Attributes*")
            while True:
                try:
                    selected = st.dataframe(
                        self.direct_attributes, hide_index=True,
                        use_container_width=True,
                        column_order=["#", "name", "optional", "cardinality", "range", "express type", "description"],
                        selection_mode="single-row", on_select="rerun",
                        key=f"{self.seed}_{self.iri}_direct_attributes")
                    break
                except:
                    self._seed += 1
            
        if selected["selection"]["rows"]:
            direct_attr_selected_index = selected["selection"]["rows"][0]
            selected = self.direct_attributes[direct_attr_selected_index]
            IfcConceptRenderer.display_selected_individual_info(selected["express type"], selected["attr datatype"], self.rdf_graph)
    
    def _display_inverse_attributes(self, container):
        with container:
            st.write(f"#### *Inverse Attributes*")
            while True:
                try:
                    selected = st.dataframe(
                        self.inverse_attributes, hide_index=True,
                        use_container_width=True,
                        column_order=["#", "name", "optional", "cardinality", "range", "express type", "description"],
                        selection_mode="single-row", on_select="rerun",
                        key=f"{self.seed}_{self.iri}_inverse_attributes")
                    break
                except:
                    self._seed += 1
        if selected["selection"]["rows"]:
            inverse_attr_selected_index = selected["selection"]["rows"][0]
            selected = self.inverse_attributes[inverse_attr_selected_index]
            IfcConceptRenderer.display_selected_individual_info(selected["express type"], selected["attr datatype"], self.rdf_graph)
    
    def _display_pset_templates(self, container):
        with container:
            st.write(f"#### *Pset Templates*")
            while True:
                try:
                    selected = st.dataframe(
                        self.pset_templates, hide_index=True, 
                        use_container_width=True,
                        column_order=["name", "express type", "definitions"],
                        selection_mode="single-row", on_select="rerun",
                        key=f"{self.seed}_{self.iri}_pset_templates")
                    break
                except:
                    self._seed += 1
    
        if selected["selection"]["rows"]:
            selected_index = selected["selection"]["rows"][0]
            selected = self.pset_templates[selected_index]
            IfcConceptRenderer.display_selected_individual_info(selected["express type"], selected["iri"], self.rdf_graph)

    def display(self, container):
        self._display_super_entities(container)
        self._display_sub_entities(container)
        self._display_direct_attributes(container)
        self._display_inverse_attributes(container)
        self._display_pset_templates(container)

class PsetInfo(ConceptInfo):
    _express_type: str = PrivateAttr("express:PropertySetTemplate")
    _props: List[Dict[str, str]] = PrivateAttr(default_factory=list)
    _applicable_entities: List[str] = PrivateAttr(default_factory=list)
    @property
    def props(self):
        return self._props
    
    @property
    def applicable_entities(self):
        return self._applicable_entities
    
    def model_post_init(self, __context):
        super().model_post_init(__context)
        
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?definitions
            WHERE {{
                <{self.iri}> <{ONT["definitions"]}> ?definitions.
            }}"""
        )
        for result_row in results:
            self._definitions = result_row.definitions
        
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?prop_name ?description ?data_type ?property_type ?dataType ?express_type
            WHERE {{
                <{self.iri}> <{ONT["hasPropTemplate"]}> ?prop .
                ?prop <{ONT["name"]}> ?prop_name;
                    <{ONT["data_type"]}> ?data_type;
                    <{ONT["description"]}> ?description;
                    <{ONT["dataType"]}> ?dataType.
                OPTIONAL {{?prop <{ONT["property_type"]}> ?property_type.}}
                ?dataType a ?express_type.
                FILTER (STRSTARTS(str(?express_type), "{ONT}"))
            }}"""
        )
        for result_row in results:
            self.props.append({
                "property": result_row.prop_name,
                "property_type": result_row.property_type,
                "data_type": result_row.data_type,
                "dataType": result_row.dataType,
                "express type": result_row.express_type.n3(self.rdf_graph.namespace_manager),
                "description": result_row.description,
            })
            
        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?applicable_entity
            WHERE {{
                <{self.iri}> <{ONT["applicableTo"]}> ?ae.
                ?ae <{ONT["superClassOf"]}>* ?applicable_entity.
            }}"""
        )
        for result_row in results:
            self.applicable_entities.append(result_row.applicable_entity)
    
    def display(self, container):
        with container:
            stoggle("Definitions", self.definitions)
            st.write(f"#### *Properties*")
            while True:
                try:
                    selected = st.dataframe(
                        self.props, hide_index=True, 
                        use_container_width=True,
                        column_order=["property", "property_type", "data_type", "express type", "description"],
                        on_select="rerun", selection_mode="single-row",
                        key=f"{self.seed}_{self.iri}_props"
                    )
                    break
                except:
                    self._seed += 1
        if selected["selection"]["rows"]:
            selected_index = selected["selection"]["rows"][0]
            prop = self.props[selected_index]
            IfcConceptRenderer.display_selected_individual_info(prop["express type"], prop["dataType"], self.rdf_graph)
            
        with container:
            st.write(f"#### *Applicable entities*")
            while True:
                try:
                    selected = st.dataframe(
                        {"name":[ae.fragment for ae in self.applicable_entities]}, hide_index=True,
                        use_container_width=True,
                        on_select="rerun", selection_mode="single-row",
                        key=f"{self.seed}_{self.iri}_applicable_entities"
                    )
                    break
                except:
                    self._seed += 1
        if selected["selection"]["rows"]:
            selected_index = selected["selection"]["rows"][0]
            entity = self.applicable_entities[selected_index]
            IfcConceptRenderer.display_selected_individual_info("express:Entity", entity, self.rdf_graph)
            

class QsetInfo(PsetInfo):
    _express_type: str = PrivateAttr("express:QuantitySetTemplate")
    
class DerivedTypeInfo(TypeInfo):
    _express_type: str = PrivateAttr("express:DerivedType")
    
    _derived_from: str = PrivateAttr(None)
    _cardinality: str = PrivateAttr(None)
    _definitions: str = PrivateAttr(None)
    
    @property
    def derived_from(self):
        return self._derived_from

    @property
    def cardinality(self):
        return self._cardinality
    
    @property
    def definitions(self):
        return self._definitions

    def model_post_init(self, __context):
        super().model_post_init(__context)

        results = self.rdf_graph.query(
            f"""PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
            PREFIX owl: <http://www.w3.org/2002/07/owl#>
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT DISTINCT ?definitions
            WHERE {{
                <{self.iri}> <{ONT["definitions"]}> ?definitions.
            }}"""
        )
        for result_row in results:
            self._definitions = result_row.definitions

        results = self.rdf_graph.query(
            f"""SELECT ?derived_from ?cardinality ?definitions
            WHERE {{
                <{self.iri}> <{ONT["derivedFrom"]}> ?derived_from;
                    <{ONT["definitions"]}> ?definitions;
                    <{ONT["cardinality"]}> ?cardinality.
            }}
            """
        )
        for result_row in results:
            derived_from = result_row.derived_from
            cardinality = result_row.cardinality
            if derived_from:
                derived_from = derived_from.fragment
            self._derived_from = derived_from
            self._cardinality = cardinality
        
    def display(self, container):
        with container:
            stoggle("Definitions", self.definitions)
            st.write(f"#### *Definitions*")
            st.markdown(f"*{self.definitions}*")
            st.write(f"#### *Derived from*")
            if str(self.cardinality) != "1":
                st.write(f"{self.cardinality} *{self.derived_from}*")
            else:
                st.write(f"*{self.derived_from}*")
        super().display(container)
            

concept_info_map: Dict[str, Type[ConceptInfo]] = {
    "express:Enum": EnumInfo,
    "express:PropertyEnumeration": PropertyEnumInfo,
    "express:Select": SelectInfo,
    "express:Entity": EntityInfo,
    "express:PropertySetTemplate": PsetInfo,
    "express:QuantitySetTemplate": QsetInfo,
    "express:DerivedType": DerivedTypeInfo
}
        
class IfcConceptRenderer:
    """Utility class for rendering IFC concepts"""
    @staticmethod
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
    
    @staticmethod
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
    
    @staticmethod
    def display_selected_individual_info(express_type, individual_iri, ifc_schema_graph: rdflib.Graph):
        if express_type not in concept_info_map:
            return
        concept_info_class = concept_info_map[express_type]
        if st.session_state.get("cached_concept_info", None) is None:
            st.session_state.cached_concept_info = {}
        if st.session_state.cached_concept_info.get(individual_iri, None) is None:
            st.session_state.cached_concept_info[individual_iri] = concept_info_class(iri=individual_iri, rdf_graph=ifc_schema_graph)
        concept_info = st.session_state.cached_concept_info[individual_iri]
        
        container = st.expander(label=f"**{concept_info.label}** - {concept_info.express_type}", expanded=True)
        with container:
            st.header(f"{concept_info.label}", divider=True)
            st.markdown(f"*{concept_info.express_type}*")
            mdlit(f"@({concept_info.label})(https://ifc43-docs.standards.buildingsmart.org/IFC/RELEASE/IFC4x3/HTML/lexical/{concept_info.label}.htm)")
        
        concept_info.display(container)
    
    @staticmethod
    def render_selected_instance_echarts(instance_iri, ontology_graph: rdflib.Graph, height=400):
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